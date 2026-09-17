"""Course resource scope and transaction-wide serialization for content/publish."""

from fastapi import HTTPException

from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.course.infrastructure.repository import CourseRepository


class CourseService:
    def __init__(self, connection, user, trace_id):
        self.connection = connection
        self.user = user
        self.trace_id = trace_id
        self.repo = CourseRepository(connection)
        self.writing = False

    async def authorize(self, course_id: int, *, write=False, draft=False):
        self.writing = write
        course = await self.repo.fetch_one(
            """SELECT id, code, title, description, status, created_by, created_at, updated_at
               FROM courses WHERE id=:id AND deleted_at IS NULL"""
            + (" FOR UPDATE" if write else ""),
            {"id": course_id},
        )
        if course is None:
            raise HTTPException(404)
        manager = "ADMIN" in self.user.roles
        if "INSTRUCTOR" in self.user.roles:
            staff = await self.repo.fetch_one(
                """SELECT id FROM course_staff WHERE course_id=:course AND user_id=:user
                   AND role='INSTRUCTOR'""",
                {"course": course_id, "user": int(self.user.id)},
            )
            manager = manager or course["created_by"] == int(self.user.id) or staff is not None
        if not manager:
            enrollment = None
            if not write and course["status"] == "PUBLISHED":
                enrollment = await self.repo.fetch_one(
                    """SELECT id FROM enrollments WHERE course_id=:course
                       AND student_id=:user AND status='ACTIVE'""",
                    {"course": course_id, "user": int(self.user.id)},
                )
            if enrollment is None:
                raise HTTPException(403)
        if draft and course["status"] != "DRAFT":
            raise HTTPException(409, "Only draft courses can be edited")
        return course

    async def audit(self, action, resource, resource_id):
        await AuditRepository(self.connection).append_log(
            actor_id=int(self.user.id),
            action=action,
            resource=resource,
            resource_id=str(resource_id),
            trace_id=self.trace_id,
        )

    async def transition(self, course_id, target):
        course = await self.authorize(course_id, write=True)
        allowed = {
            "DRAFT": {"PUBLISHED"},
            "PUBLISHED": {"DRAFT", "ARCHIVED"},
            "ARCHIVED": {"DRAFT"},
        }
        if target not in allowed[course["status"]]:
            raise HTTPException(409, "Invalid course status transition")
        if target == "PUBLISHED":
            modules = await self.repo.fetch_all(
                "SELECT id FROM modules WHERE course_id=:id AND deleted_at IS NULL FOR UPDATE",
                {"id": course_id},
            )
            lessons = await self.repo.fetch_all(
                """SELECT l.module_id, l.content FROM lessons l JOIN modules m ON m.id=l.module_id
                   WHERE m.course_id=:id AND m.deleted_at IS NULL AND l.deleted_at IS NULL
                   FOR UPDATE""",
                {"id": course_id},
            )
            # Locking reads see the latest commit even when authentication established
            # an earlier REPEATABLE READ snapshot before waiting for the course lock.
            covered = {lesson["module_id"] for lesson in lessons}
            if (
                not modules
                or any(module["id"] not in covered for module in modules)
                or any(not (lesson["content"] or "").strip() for lesson in lessons)
            ):
                raise HTTPException(409, "Each module needs lessons with non-empty content")
        await self.repo.change_status(course_id, expected=course["status"], new=target)
        await self.audit("course." + target.lower(), "course", course_id)
        await self.connection.commit()
        return await self.repo.get(course_id)
