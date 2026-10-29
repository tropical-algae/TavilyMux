from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from tavily_mux.api.dependencies import AdminDep, SessionDep
from tavily_mux.services.control import logs as log_service
from tavily_mux.services.control.models import PaginatedLogs

router = APIRouter()


@router.get("", response_model=PaginatedLogs)
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
    return log_service.list_proxy_logs(
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
