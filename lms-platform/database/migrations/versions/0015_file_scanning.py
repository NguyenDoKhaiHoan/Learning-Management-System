"""Unscanned legacy uploads remain private until a successful scan."""

from alembic import op

revision = "0015_file_scanning"
down_revision = "0014_dashboard_cache"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("lesson_resources", "submission_files"):
        op.execute(f"""ALTER TABLE {table}
            ADD COLUMN scan_status ENUM('PENDING','CLEAN','REJECTED') NOT NULL DEFAULT 'PENDING',
            ADD COLUMN scan_engine VARCHAR(32) NULL,
            ADD COLUMN scanned_at DATETIME(6) NULL""")


def downgrade():
    for table in ("submission_files", "lesson_resources"):
        op.execute(f"""ALTER TABLE {table} DROP COLUMN scanned_at,
            DROP COLUMN scan_engine, DROP COLUMN scan_status""")
