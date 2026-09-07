"""Run `python -m src.core.database.check` to verify the configured database."""

import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.config.config import get_settings
from src.core.database.database import build_engine


async def check_database() -> None:
    engine = build_engine(get_settings())
    try:
        async with asyncio.timeout(15):
            async with engine.connect() as connection:
                database = await connection.scalar(text("SELECT DATABASE()"))
                print(f"Database connection OK: {database}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(check_database())
    except (SQLAlchemyError, TimeoutError, OSError) as exc:
        original = getattr(exc, "orig", exc)
        code = (
            original.args[0] if original.args and isinstance(original.args[0], int) else "unknown"
        )
        print(f"Database connection failed (driver code: {code}). Check credentials and network.")
        raise SystemExit(1) from None
