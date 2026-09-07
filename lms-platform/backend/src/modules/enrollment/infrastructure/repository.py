"""Enrollment SQL. Eligibility/state-transition policy is owned by application."""

from datetime import datetime

from src.core.database.sql import SqlRepository, SqlRow
from src.modules.enrollment.domain.enums import CourseStaffRole, EnrollmentStatus


class EnrollmentRepository(SqlRepository):
    async def create(self, *, student_id: int, course_id: int) -> int:
        return await self.insert(
            """INSERT INTO enrollments (student_id, course_id, status)
               VALUES (:student_id, :course_id, 'PENDING')""",
            {"student_id": student_id, "course_id": course_id},
        )

    async def get(self, *, student_id: int, course_id: int) -> SqlRow | None:
        return await self.fetch_one(
            """SELECT e.id, e.student_id, e.course_id, e.status, e.completed_at
               FROM enrollments e JOIN users u ON u.id = e.student_id
               JOIN courses c ON c.id = e.course_id
               WHERE e.student_id = :student_id AND e.course_id = :course_id
                 AND u.deleted_at IS NULL AND c.deleted_at IS NULL""",
            {"student_id": student_id, "course_id": course_id},
        )

    async def change_status(
        self,
        enrollment_id: int,
        *,
        expected: EnrollmentStatus,
        new: EnrollmentStatus,
        completed_at: datetime | None = None,
    ) -> bool:
        new = EnrollmentStatus(new)
        if (new == EnrollmentStatus.COMPLETED) != (completed_at is not None):
            raise ValueError("completed_at is required only for COMPLETED")
        return bool(
            await self.execute(
                """UPDATE enrollments SET status = :new, completed_at = :completed_at
               WHERE id = :id AND status = :expected""",
                {
                    "id": enrollment_id,
                    "expected": EnrollmentStatus(expected).value,
                    "new": new.value,
                    "completed_at": completed_at,
                },
            )
        )

    async def assign_staff(self, *, course_id: int, user_id: int, role: CourseStaffRole) -> int:
        return await self.insert(
            """INSERT INTO course_staff (course_id, user_id, role)
               VALUES (:course_id, :user_id, :role)""",
            {"course_id": course_id, "user_id": user_id, "role": CourseStaffRole(role).value},
        )
