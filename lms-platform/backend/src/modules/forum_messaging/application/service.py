"""Course scoped discussion use cases."""

from fastapi import HTTPException

from src.modules.course.application.service import CourseService


class ForumService(CourseService):
    async def authorize_forum(self, course_id: int, *, write=False):
        """Use live course enrollment or an approved forum membership review.

        All forum writes take the course lock first, also used by enrollment,
        staff and moderation writes. Locking reads see the latest committed rows
        after waiting, even when authentication established an earlier snapshot.
        """
        lock = " FOR UPDATE" if write else ""
        course = await self.repo.fetch_one(
            """SELECT id,code,title,description,status,created_by,created_at,updated_at
               FROM courses WHERE id=:id AND deleted_at IS NULL""" + lock,
            {"id": course_id},
        )
        if course is None:
            raise HTTPException(404)
        manager = "ADMIN" in self.user.roles
        if "INSTRUCTOR" in self.user.roles:
            staff = await self.repo.fetch_one(
                """SELECT id FROM course_staff WHERE course_id=:course AND user_id=:user
                   AND role='INSTRUCTOR'""" + lock,
                {"course": course_id, "user": int(self.user.id)},
            )
            manager = manager or course["created_by"] == int(self.user.id) or staff is not None
        if not manager:
            review = await self.repo.fetch_one(
                """SELECT status FROM forum_membership_requests
                   WHERE course_id=:course AND user_id=:user""" + lock,
                {"course": course_id, "user": int(self.user.id)},
            )
            enrollment = await self.repo.fetch_one(
                """SELECT id,status FROM enrollments WHERE course_id=:course
                   AND student_id=:user""" + lock,
                {"course": course_id, "user": int(self.user.id)},
            )
            if course["status"] != "PUBLISHED":
                raise HTTPException(403)
            if enrollment and enrollment["status"] != "ACTIVE":
                raise HTTPException(403)
            if not enrollment and (not review or review["status"] != "APPROVED"):
                raise HTTPException(403)
            if review and review["status"] == "REJECTED":
                raise HTTPException(403)
        return course

    async def forum(self, course_id: int, *, create: bool = False):
        await self.authorize_forum(course_id, write=create)
        forum = await self.repo.fetch_one(
            "SELECT id, course_id, title, description, created_by, created_at, updated_at "
            "FROM forums WHERE course_id=:course" + (" FOR UPDATE" if create else ""),
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

    async def get_thread(self, course_id: int, thread_id: int, *, write=False):
        await self.authorize_forum(course_id, write=write)
        return await self.repo.fetch_one(
            """SELECT t.id, t.forum_id, f.course_id, t.author_id, u.username AS author_username,
                      t.title, t.body, t.status, t.created_at, t.updated_at
               FROM threads t JOIN forums f ON f.id=t.forum_id
               JOIN users u ON u.id=t.author_id
               WHERE f.course_id=:course AND t.id=:thread""" + (" FOR UPDATE" if write else ""),
            {"course": course_id, "thread": thread_id},
        )

    async def get_forum_or_404(self, course_id: int):
        forum = await self.forum(course_id, create=True)
        if forum is None:
            raise HTTPException(404, "Forum chưa được khởi tạo")
        return forum
