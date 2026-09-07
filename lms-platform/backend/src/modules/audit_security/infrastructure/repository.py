"""Append-only SQL primitives. Call in the same transaction as the audited write."""

import json
from typing import Any

from src.core.database.sql import SqlRepository
from src.modules.audit_security.domain.enums import SecurityEventType, SecuritySeverity


class AuditRepository(SqlRepository):
    async def append_log(
        self,
        *,
        actor_id: int | None,
        action: str,
        resource: str,
        trace_id: str,
        resource_id: str | None = None,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        return await self.insert(
            """INSERT INTO audit_logs
               (actor_id, action, resource, resource_id, ip_address, trace_id, details)
               VALUES (:actor_id, :action, :resource, :resource_id,
                       :ip_address, :trace_id, :details)""",
            {
                "actor_id": actor_id,
                "action": action,
                "resource": resource,
                "resource_id": resource_id,
                "ip_address": ip_address,
                "trace_id": trace_id,
                "details": json.dumps(details, ensure_ascii=False, allow_nan=False)
                if details is not None
                else None,
            },
        )

    async def append_security_event(
        self,
        *,
        actor_id: int | None,
        event_type: SecurityEventType,
        trace_id: str,
        severity: SecuritySeverity = SecuritySeverity.INFO,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        return await self.insert(
            """INSERT INTO security_events
               (actor_id, event_type, severity, ip_address, trace_id, details)
               VALUES (:actor_id, :event_type, :severity, :ip_address, :trace_id, :details)""",
            {
                "actor_id": actor_id,
                "event_type": SecurityEventType(event_type).value,
                "severity": SecuritySeverity(severity).value,
                "ip_address": ip_address,
                "trace_id": trace_id,
                "details": json.dumps(details, ensure_ascii=False, allow_nan=False)
                if details is not None
                else None,
            },
        )
