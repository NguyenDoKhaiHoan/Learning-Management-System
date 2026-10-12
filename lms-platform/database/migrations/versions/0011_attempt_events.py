"""Bounded exam telemetry with human review, independent of grading."""

from alembic import op

revision = "0011_attempt_events"
down_revision = "0010_forum_messaging"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE attempt_events (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        attempt_id BIGINT UNSIGNED NOT NULL,
        client_event_id CHAR(36) NOT NULL,
        event_type ENUM('TAB_HIDDEN','WINDOW_BLUR') NOT NULL,
        trace_id VARCHAR(64) NOT NULL,
        review_status ENUM('PENDING','REVIEWED','DISMISSED') NOT NULL DEFAULT 'PENDING',
        version INT UNSIGNED NOT NULL DEFAULT 1,
        reviewed_by BIGINT UNSIGNED NULL,
        reviewed_at DATETIME(6) NULL,
        review_note VARCHAR(1000) NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT uq_attempt_events_client UNIQUE (attempt_id,client_event_id),
        CONSTRAINT fk_attempt_events_attempt FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id)
            ON DELETE RESTRICT,
        CONSTRAINT fk_attempt_events_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id)
            ON DELETE RESTRICT,
        INDEX ix_attempt_events_review (review_status,created_at,id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")


def downgrade():
    op.execute("DROP TABLE attempt_events")
