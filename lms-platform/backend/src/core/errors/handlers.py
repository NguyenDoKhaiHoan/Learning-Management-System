"""Central public error contract: never serialize SQL, token, input or traceback."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException

from src.core.contracts import ErrorDetail, ErrorResponse

logger = logging.getLogger("lms")
CODES = {
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


class ApplicationError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status, self.code, self.message = status, code, message


def error_response(
    request: Request,
    status: int,
    *,
    code: str | None = None,
    message: str | None = None,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    trace_id = request.state.trace_id
    body = ErrorResponse(
        code=code or CODES.get(status, "HTTP_ERROR"),
        message=message or HTTPStatus(status).phrase,
        details=details or [],
        trace_id=trace_id,
    )
    return JSONResponse(
        body.model_dump(), status_code=status, headers={**(headers or {}), "X-Trace-ID": trace_id}
    )


async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    # HTTPException.detail may contain internal data; expose safe status text instead.
    return error_response(request, exc.status_code, headers=exc.headers)


async def application_error(request: Request, exc: ApplicationError) -> JSONResponse:
    return error_response(request, exc.status, code=exc.code, message=exc.message)


async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not expose input/ctx or validator messages that may embed the submitted value.
    details = [
        ErrorDetail(location=list(item["loc"]), type=item["type"], message="Invalid request value")
        for item in exc.errors()
    ]
    return error_response(request, 422, details=details)


async def database_error(request: Request, exc: Exception) -> JSONResponse:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    number = args[0] if args else None
    # Expected uniqueness/FK conflicts. Other DB failures stay generic 500/503.
    if number in (1062, 1451, 1452):
        return error_response(request, 409)
    if number in (1040, 2002, 2003, 2006, 2013):
        return error_response(request, 503)
    return await unexpected_error(request, exc)


async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "request_failed",
        extra={
            "event": "request_failed",
            "trace_id": request.state.trace_id,
            "exception_type": type(exc).__name__,
        },
    )
    return error_response(request, 500)


def register_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(ApplicationError, application_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(IntegrityError, database_error)
    app.add_exception_handler(OperationalError, database_error)
    app.add_exception_handler(Exception, unexpected_error)
