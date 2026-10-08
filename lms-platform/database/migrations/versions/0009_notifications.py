"""In-app notifications addressed to individual users."""

from alembic import op

revision = "0009_notifications"
down_revision = "0008_assessment_completion"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE notifications (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        recipient_id BIGINT UNSIGNED NOT NULL,
        course_id BIGINT UNSIGNED NULL,
        type VARCHAR(64) NOT NULL,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL,
        resource_type VARCHAR(64) NULL,
        resource_id BIGINT UNSIGNED NULL,
        is_read BOOLEAN NOT NULL DEFAULT FALSE,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        read_at DATETIME(6) NULL,
        PRIMARY KEY (id),
        CONSTRAINT fk_notifications_recipient FOREIGN KEY (recipient_id)
            REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_notifications_course FOREIGN KEY (course_id) REFERENCES courses(id),
        INDEX ix_notifications_recipient_created (recipient_id, created_at),
        INDEX ix_notifications_recipient_unread (recipient_id, is_read, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")


def downgrade():
    op.execute("DROP TABLE notifications")
