from sqlalchemy.orm import Session

from tavily_mux.common.security import SecretManager
from tavily_mux.persistence.models import SystemSettings
from tavily_mux.runtime.models import ConnectionProfile
from tavily_mux.runtime.registry import RuntimeRegistry
from tavily_mux.services.control.models import SettingsResponse, SettingsUpdate
from tavily_mux.services.control.shared import decrypt_optional, mask_proxy
from tavily_mux.services.errors import NotInitializedError


def get_settings_response(
    session: Session,
    secrets_manager: SecretManager,
) -> SettingsResponse:
    settings = _get_settings(session)
    return SettingsResponse(
        upstream_base_url=settings.upstream_base_url,
        http_proxy=mask_proxy(decrypt_optional(secrets_manager, settings.http_proxy_encrypted)),
        https_proxy=mask_proxy(
            decrypt_optional(secrets_manager, settings.https_proxy_encrypted)
        ),
        allow_direct_fallback=settings.allow_direct_fallback,
        monitor_interval_seconds=settings.monitor_interval_seconds,
        request_timeout_seconds=settings.request_timeout_seconds,
        max_attempts=settings.max_attempts,
        log_retention_days=settings.log_retention_days,
    )


def get_connection_profile(
    session: Session,
    secrets_manager: SecretManager,
) -> ConnectionProfile:
    settings = _get_settings(session)
    return ConnectionProfile(
        base_url=settings.upstream_base_url,
        http_proxy=decrypt_optional(secrets_manager, settings.http_proxy_encrypted),
        https_proxy=decrypt_optional(secrets_manager, settings.https_proxy_encrypted),
        allow_direct_fallback=settings.allow_direct_fallback,
        timeout_seconds=settings.request_timeout_seconds,
    )


def update_settings(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    payload: SettingsUpdate,
) -> SettingsResponse:
    settings = _get_settings(session)
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if field == "http_proxy":
            settings.http_proxy_encrypted = secrets_manager.encrypt(value) if value else None
        elif field == "https_proxy":
            settings.https_proxy_encrypted = secrets_manager.encrypt(value) if value else None
        elif value is not None:
            setattr(settings, field, value)
    session.commit()
    runtime.load()
    return get_settings_response(session, secrets_manager)


def _get_settings(session: Session) -> SystemSettings:
    settings = session.get(SystemSettings, 1)
    if settings is None:
        raise NotInitializedError("Settings not initialized")
    return settings
