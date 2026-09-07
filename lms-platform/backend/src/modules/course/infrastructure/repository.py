"""Course persistence only; application validates ownership and publish policy."""

from src.core.database.sql import SqlRepository, SqlRow
from src.modules.course.domain.enums import CourseStatus


class CourseRepository(SqlRepository):
    async def create(
        self,
        *,
        code: str,
        title: str,
        created_by: int,
        description: str | None = None,
    ) -> int:
        return await self.insert(
            """INSERT INTO courses (code, title, description, created_by, status)
               VALUES (:code, :title, :description, :created_by, 'DRAFT')""",
            {"code": code, "title": title, "description": description, "created_by": created_by},
        )

    async def get(self, course_id: int) -> SqlRow | None:
        return await self.fetch_one(
            """SELECT id, code, title, description, status, created_by, created_at, updated_at
               FROM courses WHERE id = :id AND deleted_at IS NULL""",
            {"id": course_id},
        )

    async def list_by_status(
        self,
        status: CourseStatus,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SqlRow]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be 1..100 and offset must be nonnegative")
        return await self.fetch_all(
            """SELECT id, code, title, status, created_by FROM courses
               WHERE status = :status AND deleted_at IS NULL
               ORDER BY id DESC LIMIT :limit OFFSET :offset""",
            {"status": CourseStatus(status).value, "limit": limit, "offset": offset},
        )

    async def change_status(
        self,
        course_id: int,
        *,
        expected: CourseStatus,
        new: CourseStatus,
    ) -> bool:
        """Compare-and-set prevents silently overwriting a concurrent status change."""
        return bool(
            await self.execute(
                """UPDATE courses SET status = :new
               WHERE id = :id AND status = :expected AND deleted_at IS NULL""",
                {
                    "id": course_id,
                    "expected": CourseStatus(expected).value,
                    "new": CourseStatus(new).value,
                },
            )
        )

    async def soft_delete(self, course_id: int) -> bool:
        return bool(
            await self.execute(
                """UPDATE courses SET deleted_at = CURRENT_TIMESTAMP(6)
               WHERE id = :id AND deleted_at IS NULL""",
                {"id": course_id},
            )
        )
