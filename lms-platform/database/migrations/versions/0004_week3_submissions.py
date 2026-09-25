"""Immutable versioned assignment submissions and private files.

Revision ID: 0004_week3_submissions
Revises: 0003_week3_assignments
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0004_week3_submissions"
down_revision: str | None = "0003_week3_assignments"
branch_labels = None
depends_on = None

OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "assignment_submissions",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("assignment_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("enrollment_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("version", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("status", sa.Enum("SUBMITTED", "LATE"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("submitted_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("submitted_by", mysql.BIGINT(unsigned=True), nullable=False),
        sa.CheckConstraint("version > 0", name=op.f("ck_assignment_submissions_version")),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name=op.f("fk_assignment_submissions_assignment_id_assignments"),
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name=op.f("fk_assignment_submissions_enrollment_id_enrollments"),
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["users.id"],
            name=op.f("fk_assignment_submissions_submitted_by_users"),
        ),
        sa.UniqueConstraint(
            "assignment_id",
            "enrollment_id",
            "version",
            name=op.f("uq_assignment_submissions_version"),
        ),
        **OPTIONS,
    )
    op.create_index(
        op.f("ix_assignment_submissions_enrollment_id"),
        "assignment_submissions",
        ["enrollment_id"],
    )
    op.create_table(
        "submission_files",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("submission_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("location", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_submission_files_positive_size")),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["assignment_submissions.id"],
            name=op.f("fk_submission_files_submission_id_assignment_submissions"),
        ),
        **OPTIONS,
    )
    op.create_index(
        op.f("ix_submission_files_submission_id"), "submission_files", ["submission_id"]
    )


def downgrade() -> None:
    op.drop_table("submission_files")
    op.drop_table("assignment_submissions")
