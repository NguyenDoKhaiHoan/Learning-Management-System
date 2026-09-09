"""ASGI correlation and structured access logs without body/query/header secrets."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

trace_context: ContextVar[str] = ContextVar("trace_id", default="")
logger = logging.getLogger("lms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", "application"),
            "trace_id": getattr(record, "trace_id", trace_context.get()),
        }
        for key in ("method", "route", "status", "duration_ms", "exception_type"):
            if hasattr(record, key):
                fields[key] = getattr(record, key)
        return json.dumps(fields, ensure_ascii=False)


def configure_logging() -> None:
    if not any(getattr(handler, "lms_json", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler.lms_json = True
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class TraceMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = Headers(scope=scope).get("x-trace-id", "")
        trace = supplied if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied) else uuid4().hex
        scope.setdefault("state", {})["trace_id"] = trace
        context_token = trace_context.set(trace)
        started, status = perf_counter(), 500

        async def send_with_trace(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Trace-ID"] = trace
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace)
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            logger.info(
                "http_request",
                extra={
                    "event": "http_request",
                    "trace_id": trace,
                    "method": scope["method"],
                    "route": route,
                    "status": status,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            trace_context.reset(context_token)
