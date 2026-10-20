"""Forum moderation metadata and membership review queue."""

from alembic import op

revision = "0017_forum_moderation"
down_revision = "0016_week7_hardening"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE threads
        ADD COLUMN moderation_reason VARCHAR(500) NULL,
        ADD COLUMN moderated_by BIGINT UNSIGNED NULL,
        ADD COLUMN moderated_at DATETIME(6) NULL,
        ADD CONSTRAINT fk_threads_moderator FOREIGN KEY (moderated_by) REFERENCES users(id)
            ON DELETE SET NULL""")
    op.execute("""ALTER TABLE messages
        ADD COLUMN moderation_reason VARCHAR(500) NULL,
        ADD COLUMN moderated_by BIGINT UNSIGNED NULL,
        ADD COLUMN moderated_at DATETIME(6) NULL,
        ADD CONSTRAINT fk_messages_moderator FOREIGN KEY (moderated_by) REFERENCES users(id)
            ON DELETE SET NULL""")
    op.execute("""CREATE TABLE forum_membership_requests (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        course_id BIGINT UNSIGNED NOT NULL,
        user_id BIGINT UNSIGNED NOT NULL,
        status ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
        reason VARCHAR(500) NULL,
        reviewed_by BIGINT UNSIGNED NULL,
        reviewed_at DATETIME(6) NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT uq_forum_membership_request UNIQUE (course_id, user_id),
        CONSTRAINT fk_forum_membership_course FOREIGN KEY (course_id) REFERENCES courses(id)
            ON DELETE CASCADE,
        CONSTRAINT fk_forum_membership_user FOREIGN KEY (user_id) REFERENCES users(id)
            ON DELETE CASCADE,
        CONSTRAINT fk_forum_membership_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id)
            ON DELETE SET NULL,
        INDEX ix_forum_membership_review (course_id, status, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")


def downgrade():
    op.execute("DROP TABLE forum_membership_requests")
    op.execute("ALTER TABLE messages DROP FOREIGN KEY fk_messages_moderator")
    op.execute(
        "ALTER TABLE messages DROP COLUMN moderated_at, DROP COLUMN moderated_by, "
        "DROP COLUMN moderation_reason"
    )
    op.execute("ALTER TABLE threads DROP FOREIGN KEY fk_threads_moderator")
    op.execute(
        "ALTER TABLE threads DROP COLUMN moderated_at, DROP COLUMN moderated_by, "
        "DROP COLUMN moderation_reason"
    )
