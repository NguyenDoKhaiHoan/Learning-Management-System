"""Question classification and immutable attempt snapshots."""

from alembic import op

revision = "0006_exam_policy"
down_revision = "0005_week4_exam_gradebook"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE question_categories (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        bank_id BIGINT UNSIGNED NOT NULL,
        name VARCHAR(255) NOT NULL,
        UNIQUE KEY uq_category_bank_name(bank_id, name),
        FOREIGN KEY (bank_id) REFERENCES question_banks(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    op.execute("""ALTER TABLE questions
        ADD category_id BIGINT UNSIGNED NULL,
        ADD difficulty ENUM('EASY','MEDIUM','HARD') NOT NULL DEFAULT 'MEDIUM',
        ADD CONSTRAINT fk_questions_category FOREIGN KEY(category_id)
        REFERENCES question_categories(id)""")
    op.execute("ALTER TABLE exams ADD allow_resume BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("""ALTER TABLE exam_blueprints
        ADD bank_id BIGINT UNSIGNED NULL,
        ADD category_id BIGINT UNSIGNED NULL,
        ADD difficulty ENUM('EASY','MEDIUM','HARD') NULL,
        ADD CONSTRAINT fk_blueprint_bank FOREIGN KEY(bank_id) REFERENCES question_banks(id),
        ADD CONSTRAINT fk_blueprint_category FOREIGN KEY(category_id)
        REFERENCES question_categories(id)""")
    op.execute("ALTER TABLE exam_attempts ADD question_snapshot JSON NULL")


def downgrade():
    # Remove referencing blueprint rows/columns before dropping classification.
    op.execute("ALTER TABLE exam_blueprints DROP FOREIGN KEY fk_blueprint_bank")
    op.execute("ALTER TABLE exam_blueprints DROP FOREIGN KEY fk_blueprint_category")
    op.execute("ALTER TABLE exam_blueprints DROP bank_id, DROP category_id, DROP difficulty")
    op.execute("ALTER TABLE exam_attempts DROP COLUMN question_snapshot")
    op.execute("ALTER TABLE exams DROP COLUMN allow_resume")
    op.execute("ALTER TABLE questions DROP FOREIGN KEY fk_questions_category")
    op.execute("ALTER TABLE questions DROP COLUMN category_id, DROP COLUMN difficulty")
    op.drop_table("question_categories")
