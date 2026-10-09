"""Course scoped discussion use cases."""

from fastapi import HTTPException

from src.modules.course.application.service import CourseService


class ForumService(CourseService):
    async def forum(self, course_id: int, *, create: bool = False):
        await self.authorize(course_id, write=False)
        forum = await self.repo.fetch_one(
            "SELECT id, course_id, title, description, created_by, created_at, updated_at "
            "FROM forums WHERE course_id=:course",
            {"course": course_id},
        )
        if forum is None and create:
            forum_id = await self.repo.insert(
                """INSERT INTO forums (course_id, title, description, created_by)
                   VALUES (:course, :title, :description, :creator)""",
                {
                    "course": course_id,
                    "title": "Thảo luận khóa học",
                    "description": "Trao đổi câu hỏi và kinh nghiệm học tập.",
                    "creator": int(self.user.id),
                },
            )
            forum = await self.repo.fetch_one(
                "SELECT id, course_id, title, description, created_by, created_at, updated_at "
                "FROM forums WHERE id=:id",
                {"id": forum_id},
            )
        return forum

    async def get_thread(self, course_id: int, thread_id: int):
        await self.authorize(course_id)
        return await self.repo.fetch_one(
            """SELECT t.id, t.forum_id, f.course_id, t.author_id, u.username AS author_username,
                      t.title, t.body, t.status, t.created_at, t.updated_at
               FROM threads t JOIN forums f ON f.id=t.forum_id
               JOIN users u ON u.id=t.author_id
               WHERE f.course_id=:course AND t.id=:thread""",
            {"course": course_id, "thread": thread_id},
        )

    async def get_forum_or_404(self, course_id: int):
        forum = await self.forum(course_id, create=True)
        if forum is None:
            raise HTTPException(404, "Forum chưa được khởi tạo")
        return forum
