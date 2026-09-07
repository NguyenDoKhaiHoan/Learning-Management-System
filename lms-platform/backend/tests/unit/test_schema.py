"""Verify frozen migrations and enforce the SQL-only runtime boundary."""

import ast
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[2]
TABLES = {
    "users",
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "refresh_tokens",
    "courses",
    "modules",
    "lessons",
    "lesson_resources",
    "enrollments",
    "course_staff",
    "audit_logs",
    "security_events",
}


def test_offline_upgrade_and_downgrade() -> None:
    output = StringIO()
    config = Config(str(BACKEND / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    for name in TABLES:
        assert f"CREATE TABLE {name} (" in sql
    assert sql.count("ENGINE=InnoDB") == 14
    assert sql.count("ON UPDATE CURRENT_TIMESTAMP(6)") == 14
    assert sql.count("CHARSET=utf8mb4") == 14
    output.truncate(0)
    output.seek(0)
    command.downgrade(config, "0001_p0:base", sql=True)
    assert output.getvalue().count("DROP TABLE") == 14


def test_runtime_has_no_orm_imports() -> None:
    for path in (BACKEND / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("sqlalchemy.orm"), path
                assert not any(
                    alias.name in {"AsyncSession", "async_sessionmaker"} for alias in node.names
                ), path
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith("sqlalchemy.orm") for alias in node.names), (
                    path
                )
