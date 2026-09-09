"""Readiness checks database availability; liveness checks the API process only."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.errors.handlers import error_response

router = APIRouter(tags=["Health"], responses=ERROR_RESPONSES)


@router.get("/livez", response_model=SuccessResponse[dict[str, str]])
async def livez(request: Request) -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(data={"status": "ok"}, trace_id=request.state.trace_id)


@router.get("/healthz", response_model=SuccessResponse[dict[str, str]])
async def healthz(request: Request) -> JSONResponse:
    try:
        async with asyncio.timeout(5):
            async with request.app.state.db_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, TimeoutError, OSError):
        # Never disclose credentials, host names or driver exceptions in HTTP output.
        return error_response(request, 503)
    return JSONResponse(
        SuccessResponse(
            data={"status": "ok", "database": "ok"}, trace_id=request.state.trace_id
        ).model_dump()
    )
