"""SQL for course content; reads consistently exclude soft-deleted ancestors."""

from src.core.database.sql import SqlRepository, SqlRow
from src.modules.learning_content.domain.enums import LessonType, ResourceType


class ContentRepository(SqlRepository):
    async def create_module(self, *, course_id: int, title: str, position: int) -> int:
        return await self.insert(
            """INSERT INTO modules (course_id, title, position)
               VALUES (:course_id, :title, :position)""",
            {"course_id": course_id, "title": title, "position": position},
        )

    async def create_lesson(
        self,
        *,
        module_id: int,
        title: str,
        position: int,
        lesson_type: LessonType,
        is_preview: bool = False,
        content: str | None = None,
    ) -> int:
        return await self.insert(
            """INSERT INTO lessons (module_id, title, position, lesson_type, is_preview, content)
               VALUES (:module_id, :title, :position, :lesson_type, :is_preview, :content)""",
            {
                "module_id": module_id,
                "title": title,
                "position": position,
                "lesson_type": LessonType(lesson_type).value,
                "is_preview": is_preview,
                "content": content,
            },
        )

    async def add_resource(
        self,
        *,
        lesson_id: int,
        title: str,
        resource_type: ResourceType,
        location: str,
        mime_type: str | None = None,
        size_bytes: int | None = None,
    ) -> int:
        return await self.insert(
            """INSERT INTO lesson_resources
               (lesson_id, title, resource_type, location, mime_type, size_bytes)
               VALUES (:lesson_id, :title, :resource_type, :location, :mime_type, :size_bytes)""",
            {
                "lesson_id": lesson_id,
                "title": title,
                "resource_type": ResourceType(resource_type).value,
                "location": location,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
            },
        )

    async def get_lesson(self, lesson_id: int) -> SqlRow | None:
        return await self.fetch_one(
            """SELECT l.id, l.module_id, m.course_id, l.title, l.position,
                      l.lesson_type, l.is_preview, l.content
               FROM lessons l JOIN modules m ON m.id = l.module_id
               JOIN courses c ON c.id = m.course_id
               WHERE l.id = :id AND l.deleted_at IS NULL
                 AND m.deleted_at IS NULL AND c.deleted_at IS NULL""",
            {"id": lesson_id},
        )

    async def list_resources(self, lesson_id: int) -> list[SqlRow]:
        return await self.fetch_all(
            """SELECT r.id, r.title, r.resource_type, r.location, r.mime_type, r.size_bytes
               FROM lesson_resources r JOIN lessons l ON l.id = r.lesson_id
               JOIN modules m ON m.id = l.module_id JOIN courses c ON c.id = m.course_id
               WHERE r.lesson_id = :id AND r.deleted_at IS NULL
                 AND l.deleted_at IS NULL AND m.deleted_at IS NULL AND c.deleted_at IS NULL
               ORDER BY r.id""",
            {"id": lesson_id},
        )
