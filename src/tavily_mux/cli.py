import argparse
import sys

import uvicorn

from tavily_mux.common.config import get_settings
from tavily_mux.services.admin_service import reset_admin_secret


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
