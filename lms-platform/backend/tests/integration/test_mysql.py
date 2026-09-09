"""Runs migrations only in a new randomly named database, never the supplied database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

from src.config.config import Settings
from src.core.database.database import build_engine
from tests.integration.auth_checks import assert_http_auth
from tests.integration.sql_repository_checks import assert_sql_repositories

pytestmark = pytest.mark.integration
BACKEND = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_mysql_migration_constraints_and_round_trip() -> None:
    url_text = os.getenv("MYSQL_TEST_ADMIN_URL")
    if not url_text:
        pytest.skip("Set MYSQL_TEST_ADMIN_URL for MySQL integration tests")
    url = make_url(url_text)
    assert url.drivername == "mysql+aiomysql"
    database = "lms_test_" + uuid4().hex
    admin = create_async_engine(url._replace(database=None), isolation_level="AUTOCOMMIT")
    engine = build_engine(
        Settings(
            _env_file=None,
            database_url=url.set(database=database).render_as_string(hide_password=False),
            jwt_secret="integration-test-secret-" + uuid4().hex,
            db_host_override=None,
        )
    )
    env = {
        **os.environ,
        "DATABASE_URL": url.set(database=database).render_as_string(hide_password=False),
        "JWT_SECRET": "integration-test-secret-" + uuid4().hex,
    }

    def alembic(*args: str) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr

    async with admin.connect() as connection:
        await connection.execute(
            text(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        )
    try:
        alembic("upgrade", "head")
        alembic("current")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO users (email, username, hashed_password) "
                    "VALUES ('student@example.com', 'student', 'test-hash')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO courses (code, title, created_by) VALUES ('C1', 'Khóa học 🎓', 1)"
                )
            )
            await connection.execute(
                text("INSERT INTO enrollments (student_id, course_id) VALUES (1, 1)")
            )
        invalid_statements = [
            ("INSERT INTO enrollments (student_id, course_id) VALUES (1, 1)", 1062),
            ("INSERT INTO enrollments (student_id, course_id) VALUES (999, 1)", 1452),
            ("DELETE FROM users WHERE id = 1", 1451),
            ("INSERT INTO modules (course_id, title, position) VALUES (1, 'Invalid', 0)", 3819),
            ("UPDATE enrollments SET status = 'COMPLETED' WHERE id = 1", 3819),
        ]
        for statement, expected_code in invalid_statements:
            # PyMySQL maps MySQL CHECK violations (3819) to OperationalError.
            with pytest.raises((IntegrityError, OperationalError)) as error:
                async with engine.begin() as connection:
                    await connection.execute(text(statement))
            assert error.value.orig.args[0] == expected_code
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT title FROM courses")) == "Khóa học 🎓"
        async with engine.connect() as connection:
            tables = (
                (
                    await connection.execute(
                        text(
                            """SELECT TABLE_NAME, ENGINE, TABLE_COLLATION
                   FROM information_schema.TABLES
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME <> 'alembic_version'"""
                        )
                    )
                )
                .mappings()
                .all()
            )
            assert len(tables) == 14
            assert all(row["ENGINE"] == "InnoDB" for row in tables)
            assert all(row["TABLE_COLLATION"] == "utf8mb4_unicode_ci" for row in tables)
        await assert_sql_repositories(engine)
        await assert_http_auth(engine)
        await engine.dispose()
        alembic("downgrade", "base")
        alembic("upgrade", "head")
        alembic("current")
    finally:
        await engine.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f"DROP DATABASE `{database}`"))
        await admin.dispose()
