import argparse
import sys
from pathlib import Path

import uvicorn
from sqlalchemy.engine import make_url

from tavily_mux.common.config import Settings, get_settings
from tavily_mux.common.security import SecretManager, generate_admin_secret, hash_admin_secret
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.migrate import upgrade_database
from tavily_mux.persistence.models import AdminCredential


def reset_admin_secret(settings: Settings, requested_secret: str | None = None) -> str:
    secret = requested_secret or generate_admin_secret()
    if len(secret) < 12:
        raise ValueError("The management key must contain at least 12 characters")

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    database_url = make_url(settings.database_url)
    database_existed = bool(
        database_url.drivername.startswith("sqlite")
        and database_url.database
        and database_url.database != ":memory:"
        and Path(database_url.database).exists()
    )
    SecretManager.load(
        settings.DATA_DIR,
        settings.MASTER_KEY,
        refuse_generation=database_existed,
    )
    if settings.AUTO_MIGRATE:
        upgrade_database(settings.database_url)
    database = Database(settings.database_url)
    try:
        with database.session() as session:
            admin = session.get(AdminCredential, 1)
            if admin is None:
                admin = AdminCredential(id=1, secret_hash=hash_admin_secret(secret))
                session.add(admin)
            else:
                admin.secret_hash = hash_admin_secret(secret)
                admin.session_version += 1
            session.commit()
    finally:
        database.close()
    return secret


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tavily-mux",
        description="Run and administer TavilyMux",
    )
    subcommands = parser.add_subparsers(dest="command")
    reset = subcommands.add_parser(
        "reset-admin-secret",
        help="reset the persisted management key and revoke existing sessions",
    )
    reset.add_argument(
        "--secret",
        help="new key (omit to generate a random key)",
    )
    return parser


def run() -> None:
    args = _parser().parse_args()
    settings = get_settings()
    if args.command == "reset-admin-secret":
        try:
            secret = reset_admin_secret(settings, args.secret)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        sys.stdout.write(f"New management key (shown once): {secret}\n")
        return

    uvicorn.run(
        "tavily_mux.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=1,
        access_log=settings.ACCESS_LOG,
        proxy_headers=True,
    )
