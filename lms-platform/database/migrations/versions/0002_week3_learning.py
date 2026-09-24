"""Week 3 private file metadata and learning progress.

Revision ID: 0002_week3_learning
Revises: 0001_p0
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0002_week3_learning"
down_revision: str | None = "0001_p0"
branch_labels = None
depends_on = None


TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def timestamps():
    return (
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.add_column("lesson_resources", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column(
        "lesson_resources", sa.Column("uploaded_by", mysql.BIGINT(unsigned=True), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_lesson_resources_uploaded_by_users"),
        "lesson_resources",
        "users",
        ["uploaded_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "completion_rules",
        sa.Column("course_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "required_lesson_percent",
            sa.Numeric(5, 2),
            server_default=sa.text("100.00"),
            nullable=False,
        ),
        sa.Column("updated_by", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "required_lesson_percent > 0 AND required_lesson_percent <= 100",
            name=op.f("ck_completion_rules_percent"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_completion_rules_course_id_courses")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_completion_rules_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_completion_rules")),
        sa.UniqueConstraint("course_id", name=op.f("uq_completion_rules_course_id")),
        **TABLE_OPTIONS,
    )

    progress_status = sa.Enum(
        "NOT_STARTED", "IN_PROGRESS", "COMPLETED", name="lessonprogressstatus"
    )
    op.create_table(
        "lesson_progress",
        sa.Column("enrollment_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("lesson_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "status", progress_status, server_default=sa.text("'NOT_STARTED'"), nullable=False
        ),
        sa.Column(
            "last_position_seconds",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            server_default="0",
        ),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("completed_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "(status = 'NOT_STARTED' AND started_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'IN_PROGRESS' AND started_at IS NOT NULL AND completed_at IS NULL) OR "
            "(status = 'COMPLETED' AND started_at IS NOT NULL AND completed_at IS NOT NULL)",
            name=op.f("ck_lesson_progress_status_times"),
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name=op.f("fk_lesson_progress_enrollment_id_enrollments"),
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["lessons.id"], name=op.f("fk_lesson_progress_lesson_id_lessons")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_progress")),
        sa.UniqueConstraint(
            "enrollment_id", "lesson_id", name=op.f("uq_lesson_progress_enrollment_lesson")
        ),
        **TABLE_OPTIONS,
    )
    op.create_index(
        op.f("ix_lesson_progress_lesson_id"), "lesson_progress", ["lesson_id"], unique=False
    )

    op.create_table(
        "course_progress",
        sa.Column("enrollment_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "completed_lessons", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_lessons", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"
        ),
        sa.Column("progress_percent", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("completed_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "completed_lessons <= total_lessons AND progress_percent >= 0 "
            "AND progress_percent <= 100",
            name=op.f("ck_course_progress_values"),
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name=op.f("fk_course_progress_enrollment_id_enrollments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_progress")),
        sa.UniqueConstraint("enrollment_id", name=op.f("uq_course_progress_enrollment_id")),
        **TABLE_OPTIONS,
    )


def downgrade() -> None:
    op.drop_table("course_progress")
    # MySQL may use this explicit index to enforce the lesson FK; DROP TABLE
    # removes both together without an invalid intermediate state.
    op.drop_table("lesson_progress")
    op.drop_table("completion_rules")
    op.drop_constraint(
        op.f("fk_lesson_resources_uploaded_by_users"), "lesson_resources", type_="foreignkey"
    )
    op.drop_column("lesson_resources", "uploaded_by")
    op.drop_column("lesson_resources", "sha256")
