"""Application factory. Schema changes are exclusively managed by Alembic."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from src.config.config import Settings, get_settings
from src.core.database.database import build_engine
from src.core.database.health import router as health_router
from src.core.errors.handlers import register_handlers
from src.core.middleware.trace import TraceMiddleware, configure_logging
from src.jobs.processors.exam_expiry import run_expiry_worker
from src.modules.assignment.presentation.router import router as assignment_router
from src.modules.course.presentation.router import router as course_router
from src.modules.enrollment.presentation.router import router as enrollment_router
from src.modules.file_management.presentation.router import router as file_router
from src.modules.gradebook.presentation.router import router as gradebook_router
from src.modules.identity_access.presentation.router import router as identity_router
from src.modules.learning_content.presentation.router import router as content_router
from src.modules.learning_progress_analytics.presentation.router import router as progress_router
from src.modules.quiz_exam.presentation.router import router as quiz_exam_router
from src.modules.user_role.presentation.permissions import router as permission_router
from src.modules.user_role.presentation.router import router as role_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(settings)
        app.state.db_engine = engine
        worker = asyncio.create_task(run_expiry_worker(engine))
        try:
            yield
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
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
    app.include_router(role_router)
    app.include_router(permission_router)
    app.include_router(course_router)
    app.include_router(content_router)
    app.include_router(file_router)
    app.include_router(progress_router)
    app.include_router(quiz_exam_router)
    app.include_router(gradebook_router)
    app.include_router(assignment_router)
    app.include_router(enrollment_router)
    return app
