"""Course content hierarchy; positions are unique within their parent."""

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.models.base import TABLE_OPTIONS, Base, SoftDeleteMixin, TrackingMixin
from src.modules.learning_content.domain.enums import LessonType, ResourceType


class CourseModule(TrackingMixin, SoftDeleteMixin, Base):
    __tablename__ = "modules"
    __table_args__ = (
        UniqueConstraint("course_id", "position"),
        CheckConstraint("position > 0", name="positive_position"),
        TABLE_OPTIONS,
    )
    course_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("courses.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(INTEGER(unsigned=True))


class Lesson(TrackingMixin, SoftDeleteMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("module_id", "position"),
        CheckConstraint("position > 0", name="positive_position"),
        CheckConstraint("is_preview IN (0, 1)", name="boolean_preview"),
        TABLE_OPTIONS,
    )
    module_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("modules.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(INTEGER(unsigned=True))
    lesson_type: Mapped[LessonType] = mapped_column(Enum(LessonType, validate_strings=True))
    is_preview: Mapped[bool] = mapped_column(Boolean, server_default="0")
    content: Mapped[str | None] = mapped_column(Text)


class LessonResource(TrackingMixin, SoftDeleteMixin, Base):
    __tablename__ = "lesson_resources"
    lesson_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("lessons.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    resource_type: Mapped[ResourceType] = mapped_column(Enum(ResourceType, validate_strings=True))
    # FILE: private object-storage key; LINK: URL validated by a future application service.
    location: Mapped[str] = mapped_column(String(2048))
    mime_type: Mapped[str | None] = mapped_column(String(127))
    size_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
