import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from tavily_mux import __version__

CONFIG_FILE_ENV = "TAVILY_MUX_CONFIG_FILE"
DEFAULT_CONFIG_FILE = Path(os.getenv(CONFIG_FILE_ENV, "config.yaml")).expanduser()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TAVILY_MUX_",
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "TavilyMux"
    VERSION: str = __version__
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    DATA_DIR: Path = Path("./data")
    DATABASE_URL: str | None = None
    WEB_ROOT: Path | None = None
    AUTO_MIGRATE: bool = True

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["text", "json"] = "text"
    ACCESS_LOG: bool = False

    ADMIN_SECRET: str | None = None
    MASTER_KEY: str | None = None
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SESSION_MAX_AGE_SECONDS: int = 24 * 60 * 60

    EVENT_QUEUE_SIZE: int = 10_000
    GLOBAL_MAX_CONCURRENCY: int = 2_000
    MAX_REQUEST_BODY_BYTES: int = 10 * 1024 * 1024
    UPSTREAM_MAX_CONNECTIONS: int = 2_000
    UPSTREAM_MAX_KEEPALIVE_CONNECTIONS: int = 500
    USAGE_CHECK_CONCURRENCY: int = 10

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"sqlite:///{(self.DATA_DIR / 'database.db').resolve()}"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_settings = YamlConfigSettingsSource(
            settings_cls=settings_cls,
            yaml_file=str(DEFAULT_CONFIG_FILE),
            yaml_file_encoding="utf-8",
        )
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_settings,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return settings


def settings_for_log() -> dict[str, Any]:
    settings = get_settings()
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "host": settings.HOST,
        "port": settings.PORT,
        "data_dir": str(settings.DATA_DIR),
        "database_url": "configured" if settings.DATABASE_URL else "default",
    }
