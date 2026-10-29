from fastapi import APIRouter, Request, Response, status

from tavily_mux.api.dependencies import AdminDep, CsrfDep, SessionDep, get_context
from tavily_mux.services.control import pools as pool_service
from tavily_mux.services.control.models import (
    PoolCreate,
    PoolCreated,
    PoolResponse,
    PoolUpdate,
)

router = APIRouter()


@router.get("", response_model=list[PoolResponse])
async def list_pools(
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> list[PoolResponse]:
    context = get_context(request)
    return pool_service.list_pools(session, context.secrets, context.runtime)


@router.post("", response_model=PoolCreated, status_code=status.HTTP_201_CREATED)
async def create_pool(
    payload: PoolCreate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> PoolCreated:
    context = get_context(request)
    return pool_service.create_pool(
        session,
        context.secrets,
        context.runtime,
        payload,
    )


@router.get("/{pool_id}", response_model=PoolResponse)
async def get_pool(
    pool_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> PoolResponse:
    context = get_context(request)
    return pool_service.get_pool(session, context.secrets, pool_id, context.runtime)


@router.patch("/{pool_id}", response_model=PoolResponse)
async def update_pool(
    pool_id: str,
    payload: PoolUpdate,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> PoolResponse:
    context = get_context(request)
    return pool_service.update_pool(
        session,
        context.secrets,
        context.runtime,
        pool_id,
        payload,
    )


@router.delete("/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pool(
    pool_id: str,
    request: Request,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> Response:
    pool_service.delete_pool(session, get_context(request).runtime, pool_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
