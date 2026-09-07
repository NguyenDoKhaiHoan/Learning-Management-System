"""SQL-only MySQL connections. Use cases own commits; repositories never commit."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    create_async_engine,
)

from src.config.config import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.sqlalchemy_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        pool_timeout=settings.db_pool_timeout,
        echo=False,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 10,
            "init_command": (
                "SET time_zone = '+00:00', "
                "sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,"
                "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'"
            ),
        },
    )


async def get_connection(request: Request) -> AsyncIterator[AsyncConnection]:
    """One connection per request; close rolls back any uncommitted SQL.

    Start `async with connection.begin()` before the first query in a write use case.
    If an earlier dependency already queried this connection, use explicit
    commit/rollback for that existing transaction instead of nesting begin().
    Never share a connection between concurrently running tasks.
    """
    engine: AsyncEngine = request.app.state.db_engine
    async with engine.connect() as connection:
        yield connection


ConnectionDependency = Annotated[AsyncConnection, Depends(get_connection)]
