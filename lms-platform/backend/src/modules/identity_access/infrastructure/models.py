"""Identity persistence. Store password hashes and SHA-256 token digests only."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.models.base import TABLE_OPTIONS, Base, SoftDeleteMixin, TrackingMixin
from src.modules.identity_access.domain.enums import UserStatus


class User(TrackingMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, validate_strings=True), server_default="INACTIVE", index=True
    )


class RefreshToken(TrackingMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        Index("ix_refresh_tokens_user_revoked", "user_id", "revoked_at"),
        TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64, collation="ascii_bin"), unique=True)
    family_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
