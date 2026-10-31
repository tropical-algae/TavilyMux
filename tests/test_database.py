from pathlib import Path

import pytest
from sqlalchemy import inspect

from tavily_mux.common.config import Settings
from tavily_mux.persistence.database import (
    Database,
    DatabaseConnectionError,
)
from tavily_mux.persistence.initialize import initialize_database
from tavily_mux.persistence.url import DatabaseConfigurationError, normalize_database_url
from tavily_mux.services.bootstrap import bootstrap_application


@pytest.mark.parametrize(
    ("value", "expected_driver"),
    [
        ("sqlite:///data.db", "sqlite+pysqlite"),
        ("mysql://user:password@db/app", "mysql+pymysql"),
        ("mysql+pymysql://user:password@db/app", "mysql+pymysql"),
        ("pgsql://user:password@db/app", "postgresql+psycopg"),
        ("postgres://user:password@db/app", "postgresql+psycopg"),
        ("postgresql://user:password@db/app", "postgresql+psycopg"),
        ("postgresql+psycopg://user:password@db/app", "postgresql+psycopg"),
    ],
)
def test_normalize_database_url_selects_bundled_driver(
    value: str,
    expected_driver: str,
) -> None:
    assert normalize_database_url(value).drivername == expected_driver


@pytest.mark.parametrize(
    ("value", "expected_backend"),
    [
        ("mysql://user:password@db/app", "mysql"),
        ("postgresql://user:password@db/app", "postgresql"),
    ],
)
def test_database_loads_external_database_driver(
    value: str,
    expected_backend: str,
) -> None:
    database = Database(value)
    try:
        assert database.engine.dialect.name == expected_backend
    finally:
        database.close()


@pytest.mark.parametrize(
    "value",
    [
        "oracle://user:password@db/app",
        "mysql+asyncmy://user:password@db/app",
        "postgresql+asyncpg://user:password@db/app",
        "not a database url",
    ],
)
def test_normalize_database_url_rejects_unsupported_or_invalid_url(value: str) -> None:
    with pytest.raises(DatabaseConfigurationError):
        normalize_database_url(value)


def test_initialize_database_migrates_new_database(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'app.db'}"

    first = initialize_database(database_url, auto_migrate=True)
    try:
        assert first.schema_existed is False
        assert inspect(first.database.engine).has_table("admin_credentials")
        assert inspect(first.database.engine).has_table("alembic_version")
    finally:
        first.database.close()

    second = initialize_database(database_url, auto_migrate=True)
    try:
        assert second.schema_existed is True
    finally:
        second.database.close()


def test_initialize_database_fails_eagerly_when_database_is_unreachable(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'missing' / 'app.db'}"

    with pytest.raises(DatabaseConnectionError, match="Unable to connect to sqlite"):
        initialize_database(database_url, auto_migrate=True)


def test_application_bootstrap_stops_before_generating_secrets_when_database_fails(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    settings = Settings(
        DATA_DIR=data_dir,
        DATABASE_URL=f"sqlite:///{tmp_path / 'missing' / 'app.db'}",
    )

    with pytest.raises(DatabaseConnectionError):
        bootstrap_application(settings)

    assert not (data_dir / "master.key").exists()
