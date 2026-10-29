from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from tavily_mux.api.errors import register_error_handlers
from tavily_mux.api.router import create_router
from tavily_mux.common.config import Settings, get_settings
from tavily_mux.common.logging import configure_logging
from tavily_mux.services.bootstrap import bootstrap_application


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
    register_error_handlers(app)
    app.include_router(create_router(settings))
    return app
