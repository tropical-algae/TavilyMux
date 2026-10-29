from fastapi import APIRouter

from tavily_mux.api.routers import (
    auth,
    dashboard,
    data_plane,
    keys,
    logs,
    pools,
    relay_keys,
    system,
    web,
)
from tavily_mux.api.routers import settings as settings_router
from tavily_mux.common.config import EndpointSettings, Settings
from tavily_mux.integrations.tavily.endpoint_catalog import endpoint_specs, is_builtin_path

CONTROL_PLANE_PREFIX = "/api/v1"
_RESERVED_EXACT_PATHS = frozenset(
    {
        "/",
        "/api",
        "/assets",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/livez",
        "/readyz",
        "/login",
        "/pools",
        "/logs",
        "/settings",
        "/usage",
        "/org-usage",
    }
)
_RESERVED_PREFIXES = (
    "/api/",
    "/assets/",
    "/docs/",
    "/redoc/",
    "/login/",
    "/pools/",
    "/logs/",
    "/settings/",
)


def create_router(settings: Settings) -> APIRouter:
    _validate_endpoint_namespace(settings.ENDPOINTS)
    specifications = endpoint_specs(settings.ENDPOINTS)

    router = APIRouter()
    router.include_router(system.router, tags=["system status"])
    router.include_router(
        auth.router,
        prefix=f"{CONTROL_PLANE_PREFIX}/auth",
        tags=["authentication"],
    )
    router.include_router(
        dashboard.router,
        prefix=f"{CONTROL_PLANE_PREFIX}/dashboard",
        tags=["dashboard"],
    )
    router.include_router(
        settings_router.router,
        prefix=f"{CONTROL_PLANE_PREFIX}/settings",
        tags=["settings"],
    )
    router.include_router(
        pools.router,
        prefix=f"{CONTROL_PLANE_PREFIX}/pools",
        tags=["account pools"],
    )
    router.include_router(
        keys.router,
        prefix=f"{CONTROL_PLANE_PREFIX}/pools/{{pool_id}}/keys",
        tags=["Tavily keys"],
    )
    router.include_router(
        relay_keys.router,
        prefix=f"{CONTROL_PLANE_PREFIX}/pools/{{pool_id}}/relay-keys",
        tags=["relay keys"],
    )
    router.include_router(
        logs.router,
        prefix=f"{CONTROL_PLANE_PREFIX}/logs",
        tags=["request logs"],
    )
    router.include_router(
        data_plane.create_router(settings.ENDPOINTS),
        tags=["Tavily relay"],
    )
    router.include_router(
        web.create_router(
            settings.WEB_ROOT,
            configured_data_paths=frozenset(spec.path for spec in specifications),
        )
    )
    return router


def _validate_endpoint_namespace(settings: EndpointSettings) -> None:
    for endpoint in settings.custom:
        path = endpoint.path
        if is_builtin_path(path):
            raise ValueError(f"custom endpoint path conflicts with a built-in route: {path}")
        if path in _RESERVED_EXACT_PATHS or path.startswith(_RESERVED_PREFIXES):
            raise ValueError(f"custom endpoint path is reserved by TavilyMux: {path}")
