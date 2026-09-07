"""Alembic async MySQL environment, with offline SQL generation support."""

import asyncio
from typing import Any

from alembic import context
from alembic.util import CommandError
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from src.config.config import get_settings

# SQL-only schema: never infer schema from ORM models or an empty MetaData.
target_metadata = None


def reject_autogenerate(
    migration_context: Any,
    revision: Any,
    directives: Any,
) -> None:
    raise CommandError(
        "SQL-only project: use 'alembic revision -m ...' and write op.execute(SQL). "
        "Autogenerate/alembic check require model metadata and are not supported."
    )


def run_migrations_offline() -> None:
    # Offline compilation needs no credentials, JWT secret or running database.
    context.configure(
        dialect_name="mysql",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=None,
        process_revision_directives=reject_autogenerate,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        get_settings().sqlalchemy_url,
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 10,
            "init_command": "SET time_zone = '+00:00'",
        },
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
