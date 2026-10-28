from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_database(database_url: str) -> None:
    config = Config()
    migration_root = Path(__file__).with_name("migrations")
    config.set_main_option("script_location", str(migration_root))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
