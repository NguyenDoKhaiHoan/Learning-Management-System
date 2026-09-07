"""Append-only by application policy; restrict UPDATE/DELETE via production DB grants."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.models.base import TABLE_OPTIONS, Base, TrackingMixin
from src.modules.audit_security.domain.enums import SecurityEventType, SecuritySeverity


class AuditLog(TrackingMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_timestamp", "actor_id", "timestamp"),
        Index("ix_audit_logs_resource_id", "resource", "resource_id"),
        TABLE_OPTIONS,
    )
    # NULL represents a system operation or an unauthenticated actor.
    actor_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), server_default=text("CURRENT_TIMESTAMP(6)"), index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45))
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class SecurityEvent(TrackingMixin, Base):
    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_actor_created", "actor_id", "created_at"),
        TABLE_OPTIONS,
    )
    actor_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    event_type: Mapped[SecurityEventType] = mapped_column(
        Enum(SecurityEventType, validate_strings=True), index=True
    )
    severity: Mapped[SecuritySeverity] = mapped_column(
        Enum(SecuritySeverity, validate_strings=True), server_default="INFO", index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45))
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
