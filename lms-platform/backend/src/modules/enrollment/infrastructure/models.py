from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.models.base import TABLE_OPTIONS, Base, TrackingMixin
from src.modules.enrollment.domain.enums import CourseStaffRole, EnrollmentStatus


class Enrollment(TrackingMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id"),
        Index("ix_enrollments_course_status", "course_id", "status"),
        CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR "
            "(status <> 'COMPLETED' AND completed_at IS NULL)",
            name="completion_consistent",
        ),
        TABLE_OPTIONS,
    )
    student_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    course_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("courses.id", ondelete="RESTRICT")
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus, validate_strings=True), server_default="PENDING", index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))


class CourseStaff(TrackingMixin, Base):
    __tablename__ = "course_staff"
    __table_args__ = (UniqueConstraint("course_id", "user_id"), TABLE_OPTIONS)
    course_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("courses.id", ondelete="RESTRICT")
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[CourseStaffRole] = mapped_column(Enum(CourseStaffRole, validate_strings=True))
