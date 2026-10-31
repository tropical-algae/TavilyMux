from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine


def has_application_schema(engine: Engine) -> bool:
    schema = inspect(engine)
    return schema.has_table("alembic_version") or schema.has_table("admin_credentials")


def upgrade_database(engine: Engine) -> None:
    config = Config()
    migration_root = Path(__file__).with_name("migrations")
    config.set_main_option("script_location", str(migration_root))

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
