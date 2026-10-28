import time
from datetime import datetime
from typing import Annotated

import httpx2
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from tavily_mux.api.control_plane.schemas import (
    AuthStatus,
    ChangeAdminSecretRequest,
    ConnectionTestResponse,
    DashboardResponse,
    LoginRequest,
    LoginResponse,
    PaginatedLogs,
    PoolCreate,
    PoolCreated,
    PoolResponse,
    PoolUpdate,
    RelayKeyCreate,
    RelayKeyCreated,
    RelayKeyResponse,
    RelayKeyUpdate,
    SettingsResponse,
    SettingsUpdate,
    TavilyKeyBulkCreate,
    TavilyKeyCreate,
    TavilyKeyResponse,
    TavilyKeyUpdate,
    UsageSnapshotResponse,
)
from tavily_mux.api.dependencies import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    get_context,
    get_session,
    require_admin,
    require_csrf,
)
from tavily_mux.persistence.models import AdminCredential
from tavily_mux.services import admin_service, control_service
from tavily_mux.services.bootstrap import ApplicationContext

router = APIRouter(prefix="/api/v1")

SessionDep = Annotated[Session, Depends(get_session)]
AdminDep = Annotated[AdminCredential, Depends(require_admin)]
CsrfDep = Annotated[None, Depends(require_csrf)]


def _set_auth_cookies(
    response: Response,
    context: ApplicationContext,
    *,
    session_token: str,
    csrf_token: str,
    remember: bool,
) -> None:
    settings = context.settings
    max_age = settings.SESSION_MAX_AGE_SECONDS if remember else None
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=max_age,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        secure=settings.COOKIE_SECURE,
        httponly=False,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> LoginResponse:
    context = get_context(request)
    admin = admin_service.authenticate_admin(session, payload.secret)
    csrf_token = admin_service.generate_csrf_token()
    session_token = context.secrets.create_session(
        admin.session_version,
        context.settings.SESSION_MAX_AGE_SECONDS,
    )
    _set_auth_cookies(
        response,
        context,
        session_token=session_token,
        csrf_token=csrf_token,
        remember=payload.remember,
    )
    return LoginResponse(csrf_token=csrf_token)


@router.get("/auth/me", response_model=AuthStatus)
async def auth_status(_: AdminDep) -> AuthStatus:
    return AuthStatus()


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, _: AdminDep, __: CsrfDep) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.put("/auth/secret", status_code=status.HTTP_204_NO_CONTENT)
async def change_admin_secret(
    payload: ChangeAdminSecretRequest,
    response: Response,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> Response:
    admin_service.change_admin_secret(
        session,
        current_secret=payload.current_secret,
        new_secret=payload.new_secret,
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> DashboardResponse:
    context = get_context(request)
    return control_service.dashboard(
        session,
        dropped_log_events=context.events.dropped_events,
        runtime=context.runtime,
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> SettingsResponse:
    context = get_context(request)
    return control_service.get_settings_response(session, context.secrets)


@router.patch("/settings", response_model=SettingsResponse)
async def update_settings(
    payload: SettingsUpdate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> SettingsResponse:
    context = get_context(request)
    return control_service.update_settings(
        session,
        context.secrets,
        context.runtime,
        payload,
    )


@router.post("/settings/test", response_model=ConnectionTestResponse)
async def check_connection(
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> ConnectionTestResponse:
    context = get_context(request)
    current = control_service.get_connection_profile(session, context.secrets)
    started = time.perf_counter()
    try:
        response = await context.clients.send(
            current,
            method="GET",
            path="/",
            headers=(),
        )
        latency_ms = (time.perf_counter() - started) * 1000
        return ConnectionTestResponse(
            ok=True,
            latency_ms=latency_ms,
            status_code=response.status_code,
            proxy_configured=bool(current.http_proxy or current.https_proxy),
            message="已连接到 Tavily 地址",
        )
    except httpx2.HTTPError as error:
        return ConnectionTestResponse(
            ok=False,
            latency_ms=(time.perf_counter() - started) * 1000,
            status_code=None,
            proxy_configured=bool(current.http_proxy or current.https_proxy),
            message=f"连接失败：{type(error).__name__}",
        )


@router.get("/pools", response_model=list[PoolResponse])
async def list_pools(
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> list[PoolResponse]:
    context = get_context(request)
    return control_service.list_pools(session, context.secrets, context.runtime)


@router.post("/pools", response_model=PoolCreated, status_code=status.HTTP_201_CREATED)
async def create_pool(
    payload: PoolCreate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> PoolCreated:
    context = get_context(request)
    return control_service.create_pool(
        session,
        context.secrets,
        context.runtime,
        payload,
    )


@router.get("/pools/{pool_id}", response_model=PoolResponse)
async def get_pool(
    pool_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> PoolResponse:
    context = get_context(request)
    return control_service.get_pool(session, context.secrets, pool_id, context.runtime)


@router.patch("/pools/{pool_id}", response_model=PoolResponse)
async def update_pool(
    pool_id: str,
    payload: PoolUpdate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> PoolResponse:
    context = get_context(request)
    return control_service.update_pool(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        payload,
    )


@router.delete("/pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pool(
    pool_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> Response:
    control_service.delete_pool(session, get_context(request).runtime, pool_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pools/{pool_id}/relay-keys", response_model=list[RelayKeyResponse])
async def list_relay_keys(
    pool_id: str,
    session: SessionDep,
    _: AdminDep,
) -> list[RelayKeyResponse]:
    return control_service.list_relay_keys(session, pool_id)


@router.post(
    "/pools/{pool_id}/relay-keys",
    response_model=RelayKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_relay_key(
    pool_id: str,
    payload: RelayKeyCreate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> RelayKeyCreated:
    context = get_context(request)
    return control_service.create_relay_key(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        payload.name,
    )


@router.patch("/pools/{pool_id}/relay-keys/{relay_id}", response_model=RelayKeyResponse)
async def update_relay_key(
    pool_id: str,
    relay_id: str,
    payload: RelayKeyUpdate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> RelayKeyResponse:
    return control_service.update_relay_key(
        session,
        get_context(request).runtime,
        pool_id,
        relay_id,
        payload,
    )


@router.delete("/pools/{pool_id}/relay-keys/{relay_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relay_key(
    pool_id: str,
    relay_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> Response:
    control_service.delete_relay_key(
        session,
        get_context(request).runtime,
        pool_id,
        relay_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pools/{pool_id}/keys", response_model=list[TavilyKeyResponse])
async def list_tavily_keys(
    pool_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> list[TavilyKeyResponse]:
    context = get_context(request)
    return control_service.list_tavily_keys(
        session,
        context.secrets,
        context.runtime,
        pool_id,
    )


@router.post(
    "/pools/{pool_id}/keys",
    response_model=TavilyKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tavily_key(
    pool_id: str,
    payload: TavilyKeyCreate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> TavilyKeyResponse:
    context = get_context(request)
    return control_service.create_tavily_key(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        payload,
    )


@router.post(
    "/pools/{pool_id}/keys/bulk",
    response_model=list[TavilyKeyResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_tavily_keys(
    pool_id: str,
    payload: TavilyKeyBulkCreate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> list[TavilyKeyResponse]:
    context = get_context(request)
    return control_service.create_tavily_keys(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        payload.keys,
    )


@router.patch("/pools/{pool_id}/keys/{key_id}", response_model=TavilyKeyResponse)
async def update_tavily_key(
    pool_id: str,
    key_id: str,
    payload: TavilyKeyUpdate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> TavilyKeyResponse:
    context = get_context(request)
    return control_service.update_tavily_key(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        key_id,
        payload,
    )


@router.post("/pools/{pool_id}/keys/{key_id}/check", response_model=TavilyKeyResponse)
async def check_tavily_key(
    pool_id: str,
    key_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> TavilyKeyResponse:
    context = get_context(request)
    pool = context.runtime.snapshot.pools.get(pool_id)
    key = pool.keys.get(key_id) if pool is not None else None
    if pool is None or key is None:
        return control_service.get_tavily_key(
            session,
            context.secrets,
            pool_id,
            key_id,
            context.runtime,
        )
    await context.usage.check_key(pool, key)
    session.expire_all()
    return control_service.get_tavily_key(
        session,
        context.secrets,
        pool_id,
        key_id,
        context.runtime,
    )


@router.delete("/pools/{pool_id}/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tavily_key(
    pool_id: str,
    key_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> Response:
    control_service.delete_tavily_key(
        session,
        get_context(request).runtime,
        pool_id,
        key_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/pools/{pool_id}/keys/{key_id}/usage",
    response_model=list[UsageSnapshotResponse],
)
async def get_key_usage(
    pool_id: str,
    key_id: str,
    session: SessionDep,
    _: AdminDep,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[UsageSnapshotResponse]:
    return control_service.list_usage_snapshots(
        session,
        pool_id,
        key_id,
        limit=limit,
    )


@router.get("/logs", response_model=PaginatedLogs)
async def list_logs(
    session: SessionDep,
    _: AdminDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    pool_id: str | None = None,
    status_code_filter: Annotated[int | None, Query(alias="status_code")] = None,
    key_id: str | None = None,
    success: bool | None = None,
    retried: bool | None = None,
    request_id: Annotated[str | None, Query(max_length=200)] = None,
    time_from: datetime | None = None,
    time_to: datetime | None = None,
) -> PaginatedLogs:
    return control_service.list_proxy_logs(
        session,
        page=page,
        page_size=page_size,
        pool_id=pool_id,
        status_code=status_code_filter,
        key_id=key_id,
        success=success,
        retried=retried,
        request_id=request_id,
        time_from=time_from,
        time_to=time_to,
    )
