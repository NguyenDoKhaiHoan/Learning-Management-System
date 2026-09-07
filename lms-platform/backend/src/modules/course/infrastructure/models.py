from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.models.base import Base, SoftDeleteMixin, TrackingMixin
from src.modules.course.domain.enums import CourseStatus


class Course(TrackingMixin, SoftDeleteMixin, Base):
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CourseStatus] = mapped_column(
        Enum(CourseStatus, validate_strings=True), server_default="DRAFT", index=True
    )
    created_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
