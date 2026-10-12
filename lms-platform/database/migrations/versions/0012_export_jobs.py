"""Durable export queue and authenticated private result metadata."""

from alembic import op

revision = "0012_export_jobs"
down_revision = "0011_attempt_events"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE export_jobs (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        requested_by BIGINT UNSIGNED NOT NULL,
        request_id CHAR(36) NOT NULL,
        kind ENUM('OVERVIEW','LEARNERS','GRADEBOOK') NOT NULL,
        course_id BIGINT UNSIGNED NULL,
        filters JSON NOT NULL,
        status ENUM('PENDING','READY','FAILED') NOT NULL DEFAULT 'PENDING',
        location VARCHAR(512) NULL,
        row_count INT UNSIGNED NULL,
        error_code VARCHAR(64) NULL,
        trace_id VARCHAR(64) NOT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        completed_at DATETIME(6) NULL,
        PRIMARY KEY (id),
        CONSTRAINT uq_export_jobs_request UNIQUE (requested_by,request_id),
        CONSTRAINT fk_export_jobs_requester FOREIGN KEY (requested_by) REFERENCES users(id)
            ON DELETE RESTRICT,
        CONSTRAINT fk_export_jobs_course FOREIGN KEY (course_id) REFERENCES courses(id)
            ON DELETE RESTRICT,
        INDEX ix_export_jobs_queue (status,created_at,id),
        INDEX ix_export_jobs_owner (requested_by,created_at,id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")


def downgrade():
    op.execute("DROP TABLE export_jobs")
