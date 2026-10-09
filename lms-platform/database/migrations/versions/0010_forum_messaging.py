"""Basic course forums with discussion threads and replies."""

from alembic import op

revision = "0010_forum_messaging"
down_revision = "0009_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE forums (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        course_id BIGINT UNSIGNED NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT NULL,
        created_by BIGINT UNSIGNED NOT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT uq_forums_course UNIQUE (course_id),
        CONSTRAINT fk_forums_course FOREIGN KEY (course_id) REFERENCES courses(id)
            ON DELETE CASCADE,
        CONSTRAINT fk_forums_creator FOREIGN KEY (created_by) REFERENCES users(id)
            ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    op.execute("""CREATE TABLE threads (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        forum_id BIGINT UNSIGNED NOT NULL,
        author_id BIGINT UNSIGNED NOT NULL,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL,
        status ENUM('OPEN','LOCKED','ARCHIVED') NOT NULL DEFAULT 'OPEN',
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT fk_threads_forum FOREIGN KEY (forum_id) REFERENCES forums(id)
            ON DELETE CASCADE,
        CONSTRAINT fk_threads_author FOREIGN KEY (author_id) REFERENCES users(id)
            ON DELETE RESTRICT,
        INDEX ix_threads_forum_updated (forum_id, updated_at, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    op.execute("""CREATE TABLE messages (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        thread_id BIGINT UNSIGNED NOT NULL,
        author_id BIGINT UNSIGNED NOT NULL,
        body TEXT NOT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6),
        deleted_at DATETIME(6) NULL,
        PRIMARY KEY (id),
        CONSTRAINT fk_messages_thread FOREIGN KEY (thread_id) REFERENCES threads(id)
            ON DELETE CASCADE,
        CONSTRAINT fk_messages_author FOREIGN KEY (author_id) REFERENCES users(id)
            ON DELETE RESTRICT,
        INDEX ix_messages_thread_created (thread_id, created_at, id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")


def downgrade():
    op.execute("DROP TABLE messages")
    op.execute("DROP TABLE threads")
    op.execute("DROP TABLE forums")
