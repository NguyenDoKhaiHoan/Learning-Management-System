"""Global RBAC. Course-scoped membership is stored separately in course_staff."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.models.base import TABLE_OPTIONS, Base, TrackingMixin


class Role(TrackingMixin, Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))


class Permission(TrackingMixin, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(500))


class UserRole(TrackingMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"), TABLE_OPTIONS)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    role_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("roles.id", ondelete="RESTRICT"), index=True
    )


class RolePermission(TrackingMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"), TABLE_OPTIONS)
    role_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("roles.id", ondelete="RESTRICT")
    )
    permission_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("permissions.id", ondelete="RESTRICT"), index=True
    )
