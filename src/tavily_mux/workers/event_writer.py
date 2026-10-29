import queue
import threading

from loguru import logger
from sqlalchemy.orm import Session

from tavily_mux.common.time import utc_now
from tavily_mux.domain.enums import KeyStatus
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.models import (
    ProxyAttempt,
    ProxyRequest,
    RelayKey,
    TaskAffinity,
    TavilyKey,
    UsageSnapshot,
)
from tavily_mux.workers.events import (
    ProxyRequestEvent,
    TaskAffinityEvent,
    UsageSnapshotEvent,
)

_STOP = object()
type PersistEvent = ProxyRequestEvent | TaskAffinityEvent | UsageSnapshotEvent


class EventWriter:
    def __init__(self, database: Database, *, queue_size: int) -> None:
        self._database = database
        self._queue: queue.Queue[PersistEvent | object] = queue.Queue(queue_size)
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
        return self._emit(event, label="request log")

    def emit_affinity(self, pool_id: str, resource_id: str, key_id: str) -> bool:
        return self._emit(
            TaskAffinityEvent(
                pool_id=pool_id,
                resource_id=resource_id,
                key_id=key_id,
            ),
            label="task affinity",
        )

    def emit_usage(self, event: UsageSnapshotEvent) -> bool:
        return self._emit(event, label="usage snapshot")

    def _emit(self, event: PersistEvent, *, label: str) -> bool:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self.dropped_events += 1
            logger.error("Persistence event queue is full; {} was dropped", label)
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

    def _write(self, events: list[PersistEvent | object]) -> None:
        state_events = [
            event
            for event in events
            if isinstance(event, ProxyRequestEvent | UsageSnapshotEvent)
        ]
        affinity_events = {
            (event.pool_id, event.resource_id): event
            for event in events
            if isinstance(event, TaskAffinityEvent)
        }
        if not state_events and not affinity_events:
            return
        try:
            with self._database.session() as session:
                for event in state_events:
                    if isinstance(event, UsageSnapshotEvent):
                        self._write_usage(session, event)
                        continue
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
                for affinity, affinity_event in affinity_events.items():
                    row = session.get(TaskAffinity, affinity)
                    if row is None:
                        session.add(
                            TaskAffinity(
                                pool_id=affinity_event.pool_id,
                                resource_id=affinity_event.resource_id,
                                key_id=affinity_event.key_id,
                            )
                        )
                    else:
                        row.key_id = affinity_event.key_id
                        row.created_at = utc_now()
                session.commit()
        except Exception:
            logger.exception("Unable to persist event batch")

    @staticmethod
    def _write_usage(session: Session, event: UsageSnapshotEvent) -> None:
        row = session.get(TavilyKey, event.key_id)
        if row is None:
            return
        row.status = event.status
        row.last_checked_at = event.checked_at
        row.last_error = event.error
        if event.status in {
            KeyStatus.AVAILABLE.value,
            KeyStatus.LOW_QUOTA.value,
            KeyStatus.EXHAUSTED.value,
        }:
            row.usage = event.usage
            row.usage_limit = event.usage_limit
            row.account_plan = event.account_plan
            row.account_plan_usage = event.account_plan_usage
            row.account_plan_limit = event.account_plan_limit
            row.paygo_usage = event.paygo_usage
            row.paygo_limit = event.paygo_limit
        session.add(
            UsageSnapshot(
                key_id=event.key_id,
                captured_at=event.checked_at,
                usage=row.usage,
                usage_limit=row.usage_limit,
                account_plan_usage=row.account_plan_usage,
                account_plan_limit=row.account_plan_limit,
                paygo_usage=row.paygo_usage,
                paygo_limit=row.paygo_limit,
                status=event.status,
            )
        )
