from fastapi import APIRouter, Request

from tavily_mux.services.bootstrap import ApplicationContext

router = APIRouter()


@router.get("/livez", include_in_schema=False)
async def livez() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(request: Request) -> dict[str, str]:
    context: ApplicationContext | None = request.app.state.context
    return {"status": "ready" if context and context.ready else "starting"}
