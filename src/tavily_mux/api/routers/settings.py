import time

import httpx2
from fastapi import APIRouter, Request

from tavily_mux.api.dependencies import AdminDep, CsrfDep, SessionDep, get_context
from tavily_mux.api.schemas.settings import ConnectionTestResponse
from tavily_mux.services.control import settings as settings_service
from tavily_mux.services.control.models import SettingsResponse, SettingsUpdate

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings(
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> SettingsResponse:
    context = get_context(request)
    return settings_service.get_settings_response(session, context.secrets)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    payload: SettingsUpdate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> SettingsResponse:
    context = get_context(request)
    return settings_service.update_settings(
        session,
        context.secrets,
        context.runtime,
        payload,
    )


@router.post("/test", response_model=ConnectionTestResponse)
async def check_connection(
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> ConnectionTestResponse:
    context = get_context(request)
    current = settings_service.get_connection_profile(session, context.secrets)
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
