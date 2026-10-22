"""Rehearse a clean MySQL migration and demo seed in a disposable database.

The rehearsal never touches the configured application database.  It creates a
database named ``lms_test_rehearsal_*``, applies every Alembic migration, runs
the idempotent demo seed, checks the migration head and fixture counts, then
drops the database unless ``--keep`` is supplied for inspection.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import string
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TARGET_PATTERN = re.compile(r"lms_test_rehearsal_[a-z0-9_]+\Z")


def parse_admin_url(raw: str) -> URL:
    url = make_url(raw)
    if url.drivername != "mysql+aiomysql" or not url.host or not url.username:
        raise ValueError("admin URL must use mysql+aiomysql and include host/user")
    return url


def target_name() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "lms_test_rehearsal_" + "".join(secrets.choice(alphabet) for _ in range(8))


def render(url: URL, database: str) -> str:
    return url.set(database=database).update_query_dict({"charset": "utf8mb4"}).render_as_string(
        hide_password=False
    )


async def database_command(admin: URL, statement: str) -> None:
    engine = create_async_engine(
        admin.set(database=None),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
        hide_parameters=True,
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


def migrate(database_url: str, jwt_secret: str) -> None:
    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": database_url,
        "JWT_SECRET": jwt_secret,
        "DB_HOST_OVERRIDE": "",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=True,
        timeout=180,
    )


async def seed_and_verify(database_url: str, jwt_secret: str) -> dict[str, object]:
    sys.path.insert(0, str(BACKEND))
    from scripts.seed_week2 import DEMO_PASSWORD, seed_demo
    from src.config.config import Settings
    from src.core.database.database import build_engine

    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=database_url,
        jwt_secret=jwt_secret,
    )
    engine: AsyncEngine = build_engine(settings)
    try:
        async with engine.begin() as connection:
            fixture = await seed_demo(connection, DEMO_PASSWORD)
            head = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
            counts = {}
            for table in ("users", "roles", "enrollments", "assignments", "exams"):
                counts[table] = int(
                    (await connection.execute(text(f"SELECT COUNT(*) FROM `{table}`"))).scalar_one()
                )
        return {"migration_head": head, "counts": counts, "fixture": fixture}
    finally:
        await engine.dispose()


async def rehearse(admin: URL, keep: bool) -> dict[str, object]:
    name = target_name()
    if not TARGET_PATTERN.fullmatch(name):
        raise AssertionError("generated rehearsal name does not satisfy the safety guard")
    database_url = render(admin, name)
    jwt_secret = secrets.token_urlsafe(48)
    await database_command(
        admin,
        f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
    )
    try:
        migrate(database_url, jwt_secret)
        result = await seed_and_verify(database_url, jwt_secret)
        if result["migration_head"] != "0017_forum_moderation":
            raise RuntimeError(f"unexpected migration head: {result['migration_head']}")
        return {"database": name, **result, "dropped": not keep}
    finally:
        if not keep:
            await database_command(admin, f"DROP DATABASE IF EXISTS `{name}`")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--admin-url",
        default=os.getenv("MYSQL_TEST_ADMIN_URL") or os.getenv("DATABASE_URL"),
        help="mysql+aiomysql administrator URL; defaults to MYSQL_TEST_ADMIN_URL",
    )
    parser.add_argument("--keep", action="store_true", help="keep the rehearsal database")
    args = parser.parse_args()
    if not args.admin_url:
        raise SystemExit("--admin-url or MYSQL_TEST_ADMIN_URL is required")
    result = asyncio.run(rehearse(parse_admin_url(args.admin_url), args.keep))
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
