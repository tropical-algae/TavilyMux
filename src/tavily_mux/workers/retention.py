import asyncio
from contextlib import suppress
from datetime import timedelta

from loguru import logger
from sqlalchemy import delete

from tavily_mux.common.time import utc_now
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.models import ProxyRequest, SystemSettings, UsageSnapshot


class RetentionWorker:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="retention-worker")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stop.set()
        await task
        self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            self.cleanup()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=3600)

    def cleanup(self) -> None:
        try:
            with self._database.session() as session:
                settings = session.get(SystemSettings, 1)
                if settings is None:
                    return
                boundary = utc_now() - timedelta(days=settings.log_retention_days)
                session.execute(delete(ProxyRequest).where(ProxyRequest.created_at < boundary))
                session.execute(
                    delete(UsageSnapshot).where(UsageSnapshot.captured_at < boundary)
                )
                session.commit()
        except Exception:
            logger.exception("Unable to clean retained request data")
