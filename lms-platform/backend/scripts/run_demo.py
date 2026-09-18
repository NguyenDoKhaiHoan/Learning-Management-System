"""Create/migrate/seed a dedicated demo database and serve the API on localhost:8002."""

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

import uvicorn
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.seed_week2 import DEMO_PASSWORD, seed_demo
from src.config.config import Settings
from src.core.database.database import build_engine
from src.main import create_app


async def prepare(settings, database):
    if settings.app_env not in {"development", "test"}:
        raise ValueError("Demo is restricted to development/test")
    if not re.fullmatch(r"lms_demo_[a-z0-9_]{1,40}", database):
        raise ValueError("LMS_DEMO_DATABASE must start with lms_demo_ and use a-z, 0-9, underscore")
    url = settings.sqlalchemy_url.set(database=database)
    admin = create_async_engine(url._replace(database=None), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            await connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
    finally:
        await admin.dispose()
    config = Settings(
        _env_file=None,
        app_env="test",
        database_url=url.render_as_string(hide_password=False),
        jwt_secret=settings.jwt_secret,
        db_host_override=None,
    )
    process = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        timeout=120,
        env={
            **os.environ,
            "DATABASE_URL": url.render_as_string(hide_password=False),
            "JWT_SECRET": settings.jwt_secret.get_secret_value(),
            "DB_HOST_OVERRIDE": "",
        },
    )
    if process.returncode:
        raise RuntimeError("Demo migration failed; check MySQL availability and schema")
    engine = build_engine(config)
    try:
        async with engine.begin() as connection:
            await seed_demo(connection, os.getenv("LMS_DEMO_PASSWORD", DEMO_PASSWORD))
    finally:
        await engine.dispose()
    return config


if __name__ == "__main__":
    config = asyncio.run(prepare(Settings(), os.getenv("LMS_DEMO_DATABASE", "lms_demo_week2")))
    print("Demo ready: demo_admin / demo_instructor / demo_student. See docs/api/week-2-demo.md.")
    uvicorn.run(
        create_app(config),
        host="127.0.0.1",
        port=int(os.getenv("LMS_DEMO_PORT", "8002")),
        access_log=False,
    )
