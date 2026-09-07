"""Readiness checks database availability; liveness checks the API process only."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["Health"])


@router.get("/livez")
async def livez() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    try:
        async with asyncio.timeout(5):
            async with request.app.state.db_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, TimeoutError, OSError):
        # Never disclose credentials, host names or driver exceptions in HTTP output.
        return JSONResponse({"status": "unavailable", "database": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "ok"})
