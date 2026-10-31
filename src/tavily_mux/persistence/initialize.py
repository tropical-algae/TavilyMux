from dataclasses import dataclass

from tavily_mux.persistence.database import Database
from tavily_mux.persistence.migrate import has_application_schema, upgrade_database


@dataclass(frozen=True, slots=True)
class DatabaseInitialization:
    database: Database
    schema_existed: bool


def initialize_database(
    database_url: str,
    *,
    auto_migrate: bool,
) -> DatabaseInitialization:
    """Connect eagerly and optionally migrate before the application starts."""
    database = Database(database_url)
    try:
        database.check_connection()
        schema_existed = has_application_schema(database.engine)
        if auto_migrate:
            upgrade_database(database.engine)
    except Exception:
        database.close()
        raise
    return DatabaseInitialization(database=database, schema_existed=schema_existed)
