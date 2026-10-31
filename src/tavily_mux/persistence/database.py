from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from tavily_mux.persistence.url import normalize_database_url


class DatabaseConnectionError(ConnectionError):
    """Raised when the configured database is unreachable at startup."""


class Database:
    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.url = normalize_database_url(url)
        self.engine = create_engine(self.url, echo=echo, pool_pre_ping=True)
        if self.url.get_backend_name() == "sqlite":
            event.listen(self.engine, "connect", _set_sqlite_pragmas)
        self.sessions = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.sessions() as session:
            yield session

    def check_connection(self) -> None:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            backend = self.url.get_backend_name()
            location = self.url.database or "configured database"
            if self.url.host:
                location = f"{self.url.host}/{location}"
            raise DatabaseConnectionError(
                f"Unable to connect to {backend} database at {location}"
            ) from error

    def close(self) -> None:
        self.engine.dispose()


def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
