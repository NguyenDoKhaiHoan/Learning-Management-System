"""Opt-in completion gates on published assessment results."""

from alembic import op

revision = "0008_assessment_completion"
down_revision = "0007_grading"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE completion_rules
        ADD require_published_assignment_grades BOOLEAN NOT NULL DEFAULT FALSE,
        ADD require_published_exam_grades BOOLEAN NOT NULL DEFAULT FALSE,
        ADD minimum_grade_percent DECIMAL(5,2) NOT NULL DEFAULT 50.00,
        ADD CONSTRAINT ck_completion_grade_percent CHECK
            (minimum_grade_percent >= 0 AND minimum_grade_percent <= 100)""")
    op.execute("""ALTER TABLE course_progress
        ADD passed_assignments INT UNSIGNED NOT NULL DEFAULT 0,
        ADD total_exams INT UNSIGNED NOT NULL DEFAULT 0,
        ADD passed_exams INT UNSIGNED NOT NULL DEFAULT 0""")


def downgrade():
    op.execute(
        "ALTER TABLE course_progress DROP passed_assignments, DROP total_exams, DROP passed_exams"
    )
    op.execute("ALTER TABLE completion_rules DROP CHECK ck_completion_grade_percent")
    op.execute("""ALTER TABLE completion_rules DROP require_published_assignment_grades,
        DROP require_published_exam_grades, DROP minimum_grade_percent""")
