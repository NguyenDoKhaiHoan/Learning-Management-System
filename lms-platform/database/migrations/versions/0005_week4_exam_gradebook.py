"""Week 4 exam core and gradebook schema.

Revision ID: 0005_week4_exam_gradebook
Revises: 0004_week3_submissions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0005_week4_exam_gradebook"
down_revision: str | None = "0004_week3_submissions"
branch_labels = None
depends_on = None

OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def timestamps():
    return (
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
    )


def upgrade() -> None:
    op.create_table(
        "question_banks",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("course_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PUBLISHED", "ARCHIVED", name="questionbankstatus"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("created_by", mysql.BIGINT(unsigned=True), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        **OPTIONS,
    )
    op.create_index("ix_question_banks_course_status", "question_banks", ["course_id", "status"])

    op.create_table(
        "questions",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("bank_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "question_type",
            sa.Enum("SINGLE", "MULTIPLE", "TRUE_FALSE", name="questiontype"),
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("points", sa.Numeric(8, 2), nullable=False, server_default="1.00"),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PUBLISHED", "ARCHIVED", name="questionstatus"),
            nullable=False,
            server_default="DRAFT",
        ),
        *timestamps(),
        sa.CheckConstraint("points > 0", name="ck_questions_positive_points"),
        sa.ForeignKeyConstraint(["bank_id"], ["question_banks.id"], ondelete="RESTRICT"),
        **OPTIONS,
    )
    op.create_index("ix_questions_bank_status", "questions", ["bank_id", "status"])

    op.create_table(
        "question_options",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("question_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("option_key", sa.String(16), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        *timestamps(),
        sa.UniqueConstraint("question_id", "option_key", name="uq_question_options_key"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        **OPTIONS,
    )

    op.create_table(
        "exams",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("course_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PUBLISHED", "CLOSED", "ARCHIVED", name="examstatus"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("opens_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("due_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("duration_seconds", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("max_attempts", mysql.INTEGER(unsigned=True), nullable=False, server_default="1"),
        sa.Column("shuffle_questions", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("show_results", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("pass_score", sa.Numeric(8, 2), nullable=False, server_default="0.00"),
        sa.Column("created_by", mysql.BIGINT(unsigned=True), nullable=False),
        *timestamps(),
        sa.CheckConstraint("opens_at < due_at", name="ck_exams_window"),
        sa.CheckConstraint("duration_seconds > 0 AND max_attempts > 0", name="ck_exams_limits"),
        sa.CheckConstraint("pass_score >= 0", name="ck_exams_pass_score"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        **OPTIONS,
    )
    op.create_index("ix_exams_course_status", "exams", ["course_id", "status"])

    op.create_table(
        "exam_blueprints",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("exam_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "question_type",
            sa.Enum("SINGLE", "MULTIPLE", "TRUE_FALSE", name="blueprintquestiontype"),
            nullable=False,
        ),
        sa.Column("question_count", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("points_each", sa.Numeric(8, 2), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "question_count > 0 AND points_each > 0", name="ck_exam_blueprints_values"
        ),
        sa.UniqueConstraint("exam_id", "question_type", name="uq_exam_blueprints_type"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        **OPTIONS,
    )

    op.create_table(
        "exam_questions",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("exam_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("question_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("position", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("points", sa.Numeric(8, 2), nullable=False),
        sa.UniqueConstraint("exam_id", "question_id", name="uq_exam_questions_question"),
        sa.UniqueConstraint("exam_id", "position", name="uq_exam_questions_position"),
        sa.CheckConstraint("position > 0 AND points > 0", name="ck_exam_questions_values"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        **OPTIONS,
    )

    op.create_table(
        "exam_attempts",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("exam_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("enrollment_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("attempt_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "IN_PROGRESS", "SUBMITTED", "AUTO_SUBMITTED", "CANCELLED", name="examattemptstatus"
            ),
            nullable=False,
            server_default="IN_PROGRESS",
        ),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("expires_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("submitted_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("score", sa.Numeric(8, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(8, 2), nullable=False),
        sa.Column(
            "server_version", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"
        ),
        *timestamps(),
        sa.CheckConstraint(
            "attempt_no > 0 AND expires_at > started_at", name="ck_exam_attempts_window"
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= max_score)", name="ck_exam_attempts_score"
        ),
        sa.UniqueConstraint(
            "exam_id", "enrollment_id", "attempt_no", name="uq_exam_attempts_number"
        ),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="RESTRICT"),
        **OPTIONS,
    )
    op.create_index("ix_exam_attempts_student_status", "exam_attempts", ["enrollment_id", "status"])

    op.create_table(
        "exam_answers",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("attempt_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("question_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("selected_option_ids", sa.JSON(), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("points_awarded", sa.Numeric(8, 2), nullable=True),
        sa.Column("answered_at", mysql.DATETIME(fsp=6), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_exam_answers_question"),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        **OPTIONS,
    )

    op.create_table(
        "gradebook_entries",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("enrollment_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "assessment_type",
            sa.Enum("ASSIGNMENT", "EXAM", name="gradeassessmenttype"),
            nullable=False,
        ),
        sa.Column("assessment_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("score", sa.Numeric(8, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(8, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PUBLISHED", name="gradestatus"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("graded_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("published_at", mysql.DATETIME(fsp=6), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "max_score > 0 AND (score IS NULL OR (score >= 0 AND score <= max_score))",
            name="ck_gradebook_scores",
        ),
        sa.UniqueConstraint(
            "enrollment_id", "assessment_type", "assessment_id", name="uq_gradebook_assessment"
        ),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["graded_by"], ["users.id"], ondelete="RESTRICT"),
        **OPTIONS,
    )
    op.create_index(
        "ix_gradebook_entries_enrollment_status", "gradebook_entries", ["enrollment_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("gradebook_entries")
    op.drop_table("exam_answers")
    op.drop_table("exam_attempts")
    op.drop_table("exam_questions")
    op.drop_table("exam_blueprints")
    op.drop_table("exams")
    op.drop_table("question_options")
    op.drop_table("questions")
    op.drop_table("question_banks")
