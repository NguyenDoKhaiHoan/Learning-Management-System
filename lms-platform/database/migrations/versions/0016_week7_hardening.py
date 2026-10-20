"""Durable notification preferences and email delivery outbox."""

from alembic import op

revision = "0016_week7_hardening"
down_revision = "0015_file_scanning"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE notification_preferences (
        user_id BIGINT UNSIGNED NOT NULL,
        email_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        event_types JSON NULL,
        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        PRIMARY KEY (user_id),
        CONSTRAINT fk_notification_preferences_user FOREIGN KEY (user_id)
            REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    op.execute("""CREATE TABLE notification_deliveries (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        notification_id BIGINT UNSIGNED NOT NULL,
        recipient_id BIGINT UNSIGNED NOT NULL,
        channel ENUM('EMAIL') NOT NULL DEFAULT 'EMAIL',
        status ENUM('PENDING','PROCESSING','SENT','FAILED') NOT NULL DEFAULT 'PENDING',
        attempt_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
        available_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        last_error VARCHAR(500) NULL,
        sent_at DATETIME(6) NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT uq_notification_delivery UNIQUE (notification_id, channel),
        CONSTRAINT fk_notification_deliveries_notification FOREIGN KEY (notification_id)
            REFERENCES notifications(id) ON DELETE CASCADE,
        CONSTRAINT fk_notification_deliveries_recipient FOREIGN KEY (recipient_id)
            REFERENCES users(id) ON DELETE CASCADE,
        INDEX ix_notification_deliveries_due (status, available_at, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")


def downgrade():
    op.execute("DROP TABLE notification_deliveries")
    op.execute("DROP TABLE notification_preferences")
