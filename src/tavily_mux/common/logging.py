import json
import logging
import sys
from typing import Any

from loguru import logger

from tavily_mux.common.config import Settings, get_settings

SENSITIVE_KEYS = {
    "admin_secret",
    "api_key",
    "authorization",
    "master_key",
    "password",
    "proxy_password",
    "secret",
    "tavily_key",
    "token",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if key.lower() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _json_sink(message: Any) -> None:
    record = message.record
    payload = {
        "time": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        **_redact(record["extra"]),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)
        logger.opt(exception=record.exc_info, depth=6).log(level, record.getMessage())


def configure_logging(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    logger.remove()
    if settings.LOG_FORMAT == "json":
        logger.add(_json_sink, level=settings.LOG_LEVEL)
    else:
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            colorize=sys.stdout.isatty(),
            backtrace=False,
            diagnose=False,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
        )

    logging.basicConfig(handlers=[InterceptHandler()], level=settings.LOG_LEVEL, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = [InterceptHandler()]
