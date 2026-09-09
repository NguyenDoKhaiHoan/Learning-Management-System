"""Application factory. Schema changes are exclusively managed by Alembic."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.config import Settings, get_settings
from src.core.database.database import build_engine
from src.core.database.health import router as health_router
from src.core.errors.handlers import register_handlers
from src.core.middleware.trace import TraceMiddleware, configure_logging
from src.modules.identity_access.presentation.router import router as identity_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(settings)
        app.state.db_engine = engine
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env in {"development", "test"} else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env in {"development", "test"} else None,
    )
    app.state.settings = settings
    app.add_middleware(TraceMiddleware)
    register_handlers(app)
    app.include_router(health_router)
    app.include_router(identity_router)
    return app
