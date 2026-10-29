from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from tavily_mux.api.dependencies import AdminDep, CsrfDep, SessionDep, get_context
from tavily_mux.services.control import keys as key_service
from tavily_mux.services.control.models import (
    TavilyKeyBulkCreate,
    TavilyKeyCreate,
    TavilyKeyResponse,
    TavilyKeyUpdate,
    UsageSnapshotResponse,
)

router = APIRouter()


@router.get("", response_model=list[TavilyKeyResponse])
async def list_tavily_keys(
    pool_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> list[TavilyKeyResponse]:
    context = get_context(request)
    return key_service.list_tavily_keys(
        session,
        context.secrets,
        context.runtime,
        pool_id,
    )


@router.post("", response_model=TavilyKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_tavily_key(
    pool_id: str,
    payload: TavilyKeyCreate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> TavilyKeyResponse:
    context = get_context(request)
    return key_service.create_tavily_key(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        payload,
    )


@router.post(
    "/bulk",
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
    return key_service.create_tavily_keys(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        payload.keys,
    )


@router.patch("/{key_id}", response_model=TavilyKeyResponse)
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
    return key_service.update_tavily_key(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        key_id,
        payload,
    )


@router.post("/{key_id}/check", response_model=TavilyKeyResponse)
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
        return key_service.get_tavily_key(
            session,
            context.secrets,
            pool_id,
            key_id,
            context.runtime,
        )
    await context.usage.check_key(pool, key)
    await context.events.flush()
    session.expire_all()
    return key_service.get_tavily_key(
        session,
        context.secrets,
        pool_id,
        key_id,
        context.runtime,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tavily_key(
    pool_id: str,
    key_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> Response:
    key_service.delete_tavily_key(
        session,
        get_context(request).runtime,
        pool_id,
        key_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{key_id}/usage", response_model=list[UsageSnapshotResponse])
async def get_key_usage(
    pool_id: str,
    key_id: str,
    session: SessionDep,
    _: AdminDep,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[UsageSnapshotResponse]:
    return key_service.list_usage_snapshots(session, pool_id, key_id, limit=limit)
