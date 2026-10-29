import queue
import threading

from loguru import logger

from tavily_mux.persistence.database import Database
from tavily_mux.persistence.models import ProxyAttempt, ProxyRequest, RelayKey, TavilyKey
from tavily_mux.workers.events import ProxyRequestEvent

_STOP = object()


class EventWriter:
    def __init__(self, database: Database, *, queue_size: int) -> None:
        self._database = database
        self._queue: queue.Queue[ProxyRequestEvent | object] = queue.Queue(queue_size)
        self._thread: threading.Thread | None = None
        self.dropped_events = 0

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._run,
                name="proxy-event-writer",
                daemon=True,
            )
            self._thread.start()

    async def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._queue.put(_STOP)
        thread.join()
        self._thread = None

    def emit(self, event: ProxyRequestEvent) -> bool:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self.dropped_events += 1
            logger.error("Proxy event queue is full; request log was dropped")
            return False
        return True

    async def flush(self) -> None:
        self._queue.join()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                self._queue.task_done()
                return
            batch = [item]
            while len(batch) < 100:
                try:
                    next_item = self._queue.get_nowait()
                except queue.Empty:
                    break
                if next_item is _STOP:
                    self._queue.task_done()
                    self._write(batch)
                    for _ in batch:
                        self._queue.task_done()
                    return
                batch.append(next_item)
            self._write(batch)
            for _ in batch:
                self._queue.task_done()

    def _write(self, events: list[ProxyRequestEvent | object]) -> None:
        typed_events = [event for event in events if isinstance(event, ProxyRequestEvent)]
        if not typed_events:
            return
        try:
            with self._database.session() as session:
                for event in typed_events:
                    request_row = ProxyRequest(
                        id=event.request_id,
                        pool_id=event.pool_id,
                        final_key_id=event.final_key_id,
                        created_at=event.created_at,
                        completed_at=event.completed_at,
                        status_code=event.status_code,
                        latency_ms=event.latency_ms,
                        attempt_count=len(event.attempts),
                        method=event.method,
                        endpoint=event.endpoint,
                        path=event.path,
                        credits=event.credits,
                        error_type=event.error_type,
                        external_request_id=event.external_request_id,
                    )
                    session.add(request_row)
                    session.flush()
                    session.add_all(
                        [
                            ProxyAttempt(
                                request_id=event.request_id,
                                key_id=attempt.key_id,
                                attempt_no=attempt.attempt_no,
                                status_code=attempt.status_code,
                                latency_ms=attempt.latency_ms,
                                error_type=attempt.error_type,
                            )
                            for attempt in event.attempts
                        ]
                    )
                    relay = session.get(RelayKey, event.relay_id)
                    if relay is not None:
                        relay.last_used_at = event.completed_at
                    for state in event.key_states:
                        key = session.get(TavilyKey, state.key_id)
                        if key is None:
                            continue
                        key.status = state.status
                        key.last_used_at = state.last_used_at
                        key.cooldown_until = state.cooldown_until
                        key.rate_limit_cooldowns = {
                            bucket: cooldown.isoformat()
                            for bucket, cooldown in state.rate_limit_cooldowns.items()
                        }
                        key.request_count = state.request_count
                        key.success_count = state.success_count
                        key.failure_count = state.failure_count
                        key.last_error = state.last_error
                session.commit()
        except Exception:
            logger.exception("Unable to persist proxy event batch")
