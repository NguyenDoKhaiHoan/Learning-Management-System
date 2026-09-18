"""Enrollment approval and staff management within the course resource boundary."""

from fastapi import HTTPException

from src.modules.course.application.service import CourseService
from src.modules.enrollment.infrastructure.repository import EnrollmentRepository


class EnrollmentService(CourseService):
    async def eligible_user(self, user_id: int, role: str):
        user = await self.repo.fetch_one(
            "SELECT id, status, deleted_at FROM users WHERE id=:id FOR UPDATE", {"id": user_id}
        )
        if user is None or user["deleted_at"] is not None:
            raise HTTPException(404)
        if user["status"] != "ACTIVE":
            raise HTTPException(409)
        assigned = await self.repo.fetch_one(
            """SELECT ur.id FROM user_roles ur JOIN roles r ON r.id=ur.role_id
               WHERE ur.user_id=:id AND r.code=:role FOR UPDATE""",
            {"id": user_id, "role": role},
        )
        if assigned is None:
            raise HTTPException(409)

    async def enroll(self, course_id: int, student_id: int, *, self_enrollment: bool):
        if self_enrollment:
            course = await self.repo.fetch_one(
                "SELECT status FROM courses WHERE id=:id AND deleted_at IS NULL FOR UPDATE",
                {"id": course_id},
            )
            if course is None:
                raise HTTPException(404)
        else:
            course = await self.authorize(course_id, write=True)
        if course["status"] != "PUBLISHED":
            raise HTTPException(409)
        await self.eligible_user(student_id, "STUDENT")
        enrollment_id = await EnrollmentRepository(self.connection).create(
            student_id=student_id, course_id=course_id
        )
        await self.audit("enrollment.request", "enrollment", enrollment_id)
        await self.connection.commit()
        return {
            "id": enrollment_id,
            "student_id": student_id,
            "course_id": course_id,
            "status": "PENDING",
            "completed_at": None,
        }

    async def set_status(self, course_id: int, student_id: int, new: str):
        course = await self.authorize(course_id, write=True)
        row = await self.repo.fetch_one(
            """SELECT e.id,e.student_id,e.course_id,e.status,e.completed_at
               FROM enrollments e JOIN users u ON u.id=e.student_id WHERE e.course_id=:course
               AND e.student_id=:student AND u.deleted_at IS NULL FOR UPDATE""",
            {"course": course_id, "student": student_id},
        )
        if row is None:
            raise HTTPException(404)
        allowed = {"PENDING": {"ACTIVE"}, "ACTIVE": {"SUSPENDED"}, "SUSPENDED": {"ACTIVE"}}
        if new not in allowed.get(row["status"], set()):
            raise HTTPException(409)
        if new == "ACTIVE":
            if course["status"] != "PUBLISHED":
                raise HTTPException(409)
            await self.eligible_user(student_id, "STUDENT")
        await EnrollmentRepository(self.connection).change_status(
            row["id"], expected=row["status"], new=new
        )
        await self.audit("enrollment." + new.lower(), "enrollment", row["id"])
        await self.connection.commit()
        return {**row, "status": new, "completed_at": None}

    async def set_staff(self, course_id: int, user_id: int, role: str | None):
        await self.authorize(course_id, write=True)
        if role is None:
            count = await self.repo.execute(
                "DELETE FROM course_staff WHERE course_id=:course AND user_id=:user",
                {"course": course_id, "user": user_id},
            )
            if not count:
                raise HTTPException(404)
        else:
            await self.eligible_user(user_id, "INSTRUCTOR")
            await self.repo.execute(
                """INSERT INTO course_staff (course_id, user_id, role) VALUES (:course,:user,:role)
                   ON DUPLICATE KEY UPDATE role=:role""",
                {"course": course_id, "user": user_id, "role": role},
            )
        await self.audit(
            "staff.assign" if role else "staff.remove",
            "course",
            course_id,
            details={"user_id": str(user_id), "role": role},
        )
        await self.connection.commit()
