"""Atomic grading, feedback items and append-only grade revisions."""

from alembic import op

revision = "0007_grading"
down_revision = "0006_exam_policy"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE exam_attempts ADD graded_at DATETIME(6) NULL")
    op.execute("""ALTER TABLE gradebook_entries
        ADD feedback TEXT NULL,
        ADD version INT UNSIGNED NOT NULL DEFAULT 1,
        ADD source_attempt_id BIGINT UNSIGNED NULL,
        ADD source_submission_id BIGINT UNSIGNED NULL,
        ADD CONSTRAINT fk_grade_attempt FOREIGN KEY(source_attempt_id) REFERENCES exam_attempts(id),
        ADD CONSTRAINT fk_grade_submission FOREIGN KEY(source_submission_id)
            REFERENCES assignment_submissions(id)""")
    op.execute("""CREATE TABLE grade_items (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        grade_id BIGINT UNSIGNED NOT NULL,
        item_key VARCHAR(64) NOT NULL,
        label TEXT NOT NULL,
        score DECIMAL(8,2) NOT NULL,
        max_score DECIMAL(8,2) NOT NULL,
        feedback TEXT NULL,
        UNIQUE KEY uq_grade_item(grade_id,item_key),
        CONSTRAINT ck_grade_item_score CHECK(max_score>0 AND score>=0 AND score<=max_score),
        FOREIGN KEY(grade_id) REFERENCES gradebook_entries(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    op.execute("""CREATE TABLE grade_history (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        grade_id BIGINT UNSIGNED NOT NULL,
        version INT UNSIGNED NOT NULL,
        action ENUM('AUTO_GRADE','DRAFT','PUBLISH','REVISE') NOT NULL,
        actor_id BIGINT UNSIGNED NULL,
        reason TEXT NULL,
        snapshot JSON NOT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        UNIQUE KEY uq_grade_history_version(grade_id,version),
        FOREIGN KEY(grade_id) REFERENCES gradebook_entries(id),
        FOREIGN KEY(actor_id) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    op.execute("CREATE INDEX ix_attempt_expiry ON exam_attempts(status,expires_at)")


def downgrade():
    op.drop_table("grade_history")
    op.drop_table("grade_items")
    op.execute("ALTER TABLE gradebook_entries DROP FOREIGN KEY fk_grade_attempt")
    op.execute("ALTER TABLE gradebook_entries DROP FOREIGN KEY fk_grade_submission")
    op.execute("""ALTER TABLE gradebook_entries DROP feedback, DROP version,
        DROP source_attempt_id, DROP source_submission_id""")
    op.execute("DROP INDEX ix_attempt_expiry ON exam_attempts")
    op.execute("ALTER TABLE exam_attempts DROP graded_at")
