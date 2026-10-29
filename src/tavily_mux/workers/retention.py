import threading
from datetime import timedelta

from loguru import logger
from sqlalchemy import delete

from tavily_mux.common.time import utc_now
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.models import (
    ProxyRequest,
    SystemSettings,
    TaskAffinity,
    UsageSnapshot,
)


class RetentionWorker:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._run,
                name="retention-worker",
                daemon=True,
            )
            self._thread.start()

    async def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._stop.set()
        thread.join()
        self._thread = None

    def _run(self) -> None:
        while not self._stop.wait(timeout=3600):
            self.cleanup()

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
                session.execute(delete(TaskAffinity).where(TaskAffinity.created_at < boundary))
                session.commit()
        except Exception:
            logger.exception("Unable to clean retained request data")
