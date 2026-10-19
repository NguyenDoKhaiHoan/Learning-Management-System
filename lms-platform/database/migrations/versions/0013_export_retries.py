"""Persist bounded retry attempts and the next eligible queue time."""

from alembic import op

revision = "0013_export_retries"
down_revision = "0012_export_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE export_jobs
        ADD COLUMN attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
        ADD COLUMN available_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        ADD INDEX ix_export_jobs_due (status,available_at,id)""")


def downgrade():
    op.execute("""ALTER TABLE export_jobs DROP INDEX ix_export_jobs_due,
        DROP COLUMN available_at, DROP COLUMN attempt_count""")
