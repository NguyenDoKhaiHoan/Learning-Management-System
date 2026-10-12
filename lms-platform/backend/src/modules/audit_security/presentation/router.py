"""Admin-only, paginated read access to immutable audit records."""

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import require_roles
from src.modules.audit_security.domain.enums import SecurityEventType, SecuritySeverity
from src.modules.audit_security.infrastructure.repository import AuditRepository

router = APIRouter(
    prefix="/api/v1/audit",
    tags=["Audit"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_roles(["ADMIN"]))],
)


def public_records(rows):
    for row in rows:
        for key in ("id", "actor_id"):
            if row.get(key) is not None:
                row[key] = str(row[key])
        row["details"] = json.loads(row["details"]) if row["details"] else None
    return rows


@router.get("/logs", response_model=SuccessResponse[dict])
async def logs(
    request: Request,
    connection: ConnectionDependency,
    actor_id: Annotated[int | None, Query(gt=0)] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    resource: Annotated[str | None, Query(max_length=100)] = None,
    resource_id: Annotated[str | None, Query(max_length=64)] = None,
    trace_id: Annotated[str | None, Query(max_length=64)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    from datetime import UTC

    def utc(value):
        return value.astimezone(UTC).replace(tzinfo=None) if value and value.tzinfo else value

    params = {
        "actor": actor_id,
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "trace": trace_id,
        "since": utc(since),
        "until": utc(until),
        "limit": limit,
        "offset": offset,
    }
    where = """WHERE (:actor IS NULL OR actor_id=:actor)
        AND (:action IS NULL OR action=:action) AND (:resource IS NULL OR resource=:resource)
        AND (:resource_id IS NULL OR resource_id=:resource_id)
        AND (:trace IS NULL OR trace_id=:trace) AND (:since IS NULL OR timestamp>=:since)
        AND (:until IS NULL OR timestamp<=:until)"""
    repo = AuditRepository(connection)
    count = await repo.fetch_one("SELECT COUNT(*) total FROM audit_logs " + where, params)
    rows = await repo.fetch_all(
        "SELECT id,actor_id,action,resource,resource_id,ip_address,trace_id,details,timestamp "
        "FROM audit_logs " + where + " ORDER BY timestamp DESC,id DESC LIMIT :limit OFFSET :offset",
        params,
    )
    return SuccessResponse(
        data={
            "items": public_records(rows),
            "total": count["total"],
            "limit": limit,
            "offset": offset,
        },
        trace_id=request.state.trace_id,
    )


@router.get("/security-events", response_model=SuccessResponse[dict])
async def security_events(
    request: Request,
    connection: ConnectionDependency,
    event_type: SecurityEventType | None = None,
    severity: SecuritySeverity | None = None,
    actor_id: Annotated[int | None, Query(gt=0)] = None,
    trace_id: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    params = {
        "type": event_type,
        "severity": severity,
        "actor": actor_id,
        "trace": trace_id,
        "limit": limit,
        "offset": offset,
    }
    where = """WHERE (:type IS NULL OR event_type=:type)
        AND (:severity IS NULL OR severity=:severity) AND (:actor IS NULL OR actor_id=:actor)
        AND (:trace IS NULL OR trace_id=:trace)"""
    repo = AuditRepository(connection)
    count = await repo.fetch_one("SELECT COUNT(*) total FROM security_events " + where, params)
    rows = await repo.fetch_all(
        "SELECT id,actor_id,event_type,severity,ip_address,trace_id,details,created_at "
        "FROM security_events "
        + where
        + " ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset",
        params,
    )
    return SuccessResponse(
        data={
            "items": public_records(rows),
            "total": count["total"],
            "limit": limit,
            "offset": offset,
        },
        trace_id=request.state.trace_id,
    )
