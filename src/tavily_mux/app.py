from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from mimetypes import guess_type

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import Response
from loguru import logger

from tavily_mux.api.control_plane import router as control_plane_router
from tavily_mux.api.data_plane import create_data_plane_router
from tavily_mux.common.config import Settings, get_settings
from tavily_mux.common.logging import configure_logging
from tavily_mux.domain.endpoints import endpoint_specs, is_builtin_path
from tavily_mux.services.bootstrap import ApplicationContext, bootstrap_application


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info("Starting TavilyMux {}", settings.VERSION)
    context = bootstrap_application(settings)
    app.state.context = context
    await context.start()
    try:
        yield
    finally:
        await context.close()
        logger.info("TavilyMux stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.context = None
    app.include_router(create_data_plane_router(settings.ENDPOINTS))
    app.include_router(control_plane_router)

    @app.get("/livez", include_in_schema=False)
    async def livez() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> dict[str, str]:
        context: ApplicationContext | None = app.state.context
        return {"status": "ready" if context and context.ready else "starting"}

    web_root = settings.WEB_ROOT
    if web_root is not None and (web_root / "index.html").is_file():
        resolved_root = web_root.resolve()
        web_files = {
            item.relative_to(resolved_root).as_posix(): (
                item.read_bytes(),
                guess_type(item.name)[0] or "application/octet-stream",
            )
            for item in resolved_root.rglob("*")
            if item.is_file()
        }

        @app.get("/{path:path}", include_in_schema=False)
        async def web_application(path: str) -> Response:
            request_path = f"/{path}"
            configured_paths = {spec.path for spec in endpoint_specs(settings.ENDPOINTS)}
            if path not in web_files and (
                is_builtin_path(request_path)
                or request_path in configured_paths
                or request_path
                in {
                    "/api",
                    "/assets",
                    "/docs",
                    "/redoc",
                    "/openapi.json",
                    "/livez",
                    "/readyz",
                    "/usage",
                    "/org-usage",
                }
                or request_path.startswith(("/api/", "/assets/"))
            ):
                raise HTTPException(status.HTTP_404_NOT_FOUND)
            content, media_type = web_files.get(path, web_files["index.html"])
            cache_control = (
                "public, max-age=31536000, immutable"
                if path.startswith("assets/") and path in web_files
                else "no-cache"
            )
            return Response(
                content=content,
                media_type=media_type,
                headers={"Cache-Control": cache_control},
            )

    return app
