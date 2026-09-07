"""Small SQL execution adapter, with no ORM entities or query builder.

SQL strings must be developer-owned constants. Pass user input separately through
named parameters (:email, :user_id); never interpolate it into SQL text/identifiers.
Returned dictionaries are snapshots, not tracked entities. No implicit writes.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

SqlRow = dict[str, Any]
SqlParams = Mapping[str, Any]


class SqlRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def fetch_one(self, sql: str, params: SqlParams | None = None) -> SqlRow | None:
        result = await self.connection.execute(text(sql), dict(params or {}))
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None

    async def fetch_all(self, sql: str, params: SqlParams | None = None) -> list[SqlRow]:
        result = await self.connection.execute(text(sql), dict(params or {}))
        return [dict(row) for row in result.mappings()]

    async def insert(self, sql: str, params: SqlParams) -> int:
        """MySQL returns the AUTO_INCREMENT id on the same connection/cursor."""
        result = await self.connection.execute(text(sql), dict(params))
        if result.lastrowid is None:
            raise RuntimeError("INSERT did not return an AUTO_INCREMENT id")
        return int(result.lastrowid)

    async def execute(self, sql: str, params: SqlParams) -> int:
        """Return affected/matched rows; caller handles missing rows/conflicts."""
        result = await self.connection.execute(text(sql), dict(params))
        return result.rowcount
