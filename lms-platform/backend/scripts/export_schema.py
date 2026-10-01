"""Export the complete migration history into the single UTF-8 lms.sql file."""

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config


def main():
    backend = Path(__file__).resolve().parents[1]
    output = StringIO()
    command.upgrade(Config(str(backend / "alembic.ini"), output_buffer=output), "head", sql=True)
    sql = output.getvalue()
    header = (
        "-- Canonical LMS schema. MySQL 8.0.16+; UTF-8.\n"
        "-- Fresh empty lms database only. Existing databases: alembic upgrade head.\n"
        "CREATE DATABASE IF NOT EXISTS lms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
        "USE lms;\n"
        "SET time_zone = '+00:00';\n\n"
    )
    target = backend.parent / "database/schemas/shared/lms.sql"
    target.write_text(header + sql, encoding="utf-8")
    print("Updated database/schemas/shared/lms.sql")


if __name__ == "__main__":
    main()
