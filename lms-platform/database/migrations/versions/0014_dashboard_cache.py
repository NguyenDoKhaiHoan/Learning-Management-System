"""Transactionally version dashboard aggregates across API processes."""

from alembic import op

revision = "0014_dashboard_cache"
down_revision = "0013_export_retries"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE cache_versions (
        id TINYINT UNSIGNED NOT NULL,
        version BIGINT UNSIGNED NOT NULL DEFAULT 0,
        PRIMARY KEY (id),
        CONSTRAINT ck_cache_versions_singleton CHECK (id=1)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    op.execute("INSERT INTO cache_versions(id,version) VALUES (1,0)")


def downgrade():
    op.execute("DROP TABLE cache_versions")
