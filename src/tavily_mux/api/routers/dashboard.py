from fastapi import APIRouter, Request

from tavily_mux.api.dependencies import AdminDep, SessionDep, get_context
from tavily_mux.services.control import dashboard as dashboard_service
from tavily_mux.services.control.models import DashboardResponse

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def dashboard(
    request: Request,
    session: SessionDep,
    _: AdminDep,
) -> DashboardResponse:
    context = get_context(request)
    return dashboard_service.dashboard(
        session,
        dropped_log_events=context.events.dropped_events,
        runtime=context.runtime,
    )
