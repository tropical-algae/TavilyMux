from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

DATABASE_DRIVERS = {
    "mysql": "mysql+pymysql",
    "pgsql": "postgresql+psycopg",
    "postgres": "postgresql+psycopg",
    "postgresql": "postgresql+psycopg",
    "sqlite": "sqlite+pysqlite",
}
SUPPORTED_DRIVERS = frozenset(DATABASE_DRIVERS.values())


class DatabaseConfigurationError(ValueError):
    """Raised when DATABASE_URL cannot be handled by TavilyMux."""


def normalize_database_url(value: str) -> URL:
    """Resolve a concise database URL to the synchronous driver shipped by TavilyMux."""
    try:
        url = make_url(value.strip())
    except ArgumentError as error:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not a valid SQLAlchemy URL"
        ) from error

    drivername = DATABASE_DRIVERS.get(url.drivername, url.drivername)
    if drivername not in SUPPORTED_DRIVERS:
        supported = ", ".join(sorted(DATABASE_DRIVERS))
        raise DatabaseConfigurationError(
            f"Unsupported DATABASE_URL driver {url.drivername!r}; supported schemes: {supported}"
        )
    return url.set(drivername=drivername)
