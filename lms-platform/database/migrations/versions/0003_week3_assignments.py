"""Assignment policy and immutable versioned submissions.

Revision ID: 0003_week3_assignments
Revises: 0002_week3_learning
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0003_week3_assignments"
down_revision: str | None = "0002_week3_learning"
branch_labels = None
depends_on = None

OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.add_column(
        "completion_rules",
        sa.Column(
            "require_submitted_assignments",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "course_progress",
        sa.Column(
            "completed_assignments",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "course_progress",
        sa.Column(
            "total_assignments", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"
        ),
    )
    op.create_table(
        "assignments",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("course_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("opens_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("due_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("allow_late", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("late_until", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("max_attempts", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("max_file_bytes", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("allowed_mime_types", sa.String(500), nullable=False),
        sa.Column("max_score", sa.Numeric(8, 2), nullable=False),
        sa.Column("created_by", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column("deleted_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.CheckConstraint("opens_at < due_at", name=op.f("ck_assignments_window")),
        sa.CheckConstraint(
            "(allow_late=0 AND late_until IS NULL) OR (allow_late=1 AND late_until > due_at)",
            name=op.f("ck_assignments_late_policy"),
        ),
        sa.CheckConstraint(
            "max_attempts > 0 AND max_file_bytes > 0 AND max_score > 0",
            name=op.f("ck_assignments_limits"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_assignments_course_id_courses")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_assignments_created_by_users")
        ),
        **OPTIONS,
    )
    op.create_index(op.f("ix_assignments_course_id"), "assignments", ["course_id", "status"])


def downgrade() -> None:
    op.drop_table("assignments")
    op.drop_column("course_progress", "total_assignments")
    op.drop_column("course_progress", "completed_assignments")
    op.drop_column("completion_rules", "require_submitted_assignments")
