"""Content mutations serialize on the parent course, including reordering/publishing."""

from fastapi import HTTPException

from src.modules.course.application.service import CourseService
from src.modules.learning_content.infrastructure.repository import ContentRepository


class ContentService(CourseService):
    async def module(self, course_id, module_id):
        row = await self.repo.fetch_one(
            """SELECT id, title, position FROM modules
               WHERE id=:id AND course_id=:course AND deleted_at IS NULL"""
            + (" FOR UPDATE" if self.writing else ""),
            {"id": module_id, "course": course_id},
        )
        if row is None:
            raise HTTPException(404)
        return row

    async def lesson(self, course_id, module_id, lesson_id):
        await self.module(course_id, module_id)
        row = await ContentRepository(self.connection).get_lesson(
            lesson_id, for_update=self.writing
        )
        if row is None or row["module_id"] != module_id:
            raise HTTPException(404)
        return row

    async def next_position(self, kind, parent_id):
        table, parent = {"module": ("modules", "course_id"), "lesson": ("lessons", "module_id")}[
            kind
        ]
        row = await self.repo.fetch_one(
            f"SELECT COALESCE(MAX(position), 0) + 1 AS position FROM {table} "
            f"WHERE {parent}=:id FOR UPDATE",
            {"id": parent_id},
        )
        if row["position"] > 4294967295:
            raise HTTPException(409, "Position capacity exceeded")
        return row["position"]

    async def reorder(self, kind, parent_id, ids):
        # Identifiers come exclusively from this fixed developer-owned map.
        table, parent = {"module": ("modules", "course_id"), "lesson": ("lessons", "module_id")}[
            kind
        ]
        rows = await self.repo.fetch_all(
            f"SELECT id, position, deleted_at FROM {table} "
            f"WHERE {parent}=:id ORDER BY id FOR UPDATE",
            {"id": parent_id},
        )
        live_ids = {row["id"] for row in rows if row["deleted_at"] is None}
        if len(ids) != len(set(ids)) or set(ids) != live_ids:
            raise HTTPException(422, "Order must contain every active sibling exactly once")
        highest = max((row["position"] for row in rows), default=0)
        if highest + len(rows) > 4294967295:
            raise HTTPException(409, "Position capacity exceeded")
        # Stage all rows (including tombstones) outside the final range to permit swaps.
        for position, row in enumerate(rows, highest + 1):
            await self.repo.execute(
                f"UPDATE {table} SET position=:position WHERE id=:id",
                {"position": position, "id": row["id"]},
            )
        for position, row_id in enumerate(ids, 1):
            await self.repo.execute(
                f"UPDATE {table} SET position=:position WHERE id=:id",
                {"position": position, "id": row_id},
            )
        await self.audit(kind + ".reorder", kind, parent_id)
        await self.connection.commit()

    async def finish(self, action, resource, resource_id):
        await self.audit(action, resource, resource_id)
        await self.connection.commit()
