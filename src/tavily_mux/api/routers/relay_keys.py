from fastapi import APIRouter, Request, Response, status

from tavily_mux.api.dependencies import AdminDep, CsrfDep, SessionDep, get_context
from tavily_mux.services.control import relay_keys as relay_key_service
from tavily_mux.services.control.models import (
    RelayKeyCreate,
    RelayKeyCreated,
    RelayKeyResponse,
    RelayKeyUpdate,
)

router = APIRouter()


@router.get("", response_model=list[RelayKeyResponse])
async def list_relay_keys(
    pool_id: str,
    session: SessionDep,
    _: AdminDep,
) -> list[RelayKeyResponse]:
    return relay_key_service.list_relay_keys(session, pool_id)


@router.post("", response_model=RelayKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_relay_key(
    pool_id: str,
    payload: RelayKeyCreate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> RelayKeyCreated:
    context = get_context(request)
    return relay_key_service.create_relay_key(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        payload.name,
    )


@router.patch("/{relay_id}", response_model=RelayKeyResponse)
async def update_relay_key(
    pool_id: str,
    relay_id: str,
    payload: RelayKeyUpdate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> RelayKeyResponse:
    return relay_key_service.update_relay_key(
        session,
        get_context(request).runtime,
        pool_id,
        relay_id,
        payload,
    )


@router.delete("/{relay_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relay_key(
    pool_id: str,
    relay_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> Response:
    relay_key_service.delete_relay_key(
        session,
        get_context(request).runtime,
        pool_id,
        relay_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
