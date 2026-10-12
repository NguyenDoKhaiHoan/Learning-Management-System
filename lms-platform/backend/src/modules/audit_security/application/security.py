"""Persist denial metadata independently of rolled-back business writes."""

import logging
from ipaddress import ip_address

from src.modules.audit_security.domain.enums import SecurityEventType, SecuritySeverity
from src.modules.audit_security.infrastructure.repository import AuditRepository


def request_ip(request):
    try:
        return str(ip_address(request.client.host)) if request.client else None
    except ValueError:
        return None


async def record_denial(request, status):
    if status not in (401, 403) or not request.url.path.startswith("/api/v1/"):
        return
    if getattr(request.state, "security_recorded", False):
        return
    engine = getattr(request.app.state, "db_engine", None)
    if engine is None:
        return
    try:
        async with engine.begin() as connection:
            await AuditRepository(connection).append_security_event(
                actor_id=getattr(request.state, "audit_actor_id", None),
                event_type=SecurityEventType.ACCESS_DENIED,
                severity=SecuritySeverity.WARNING,
                ip_address=request_ip(request),
                trace_id=request.state.trace_id,
                details={
                    "status": status,
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", "unmatched"),
                },
            )
    except Exception:
        # A database failure must never turn a denied request into an authorized one.
        logging.getLogger("lms").error("Security event persistence failed")
