"""SQL persistence for lesson/course progress and completion rules."""

from src.core.database.sql import SqlRepository


class ProgressRepository(SqlRepository):
    async def active_enrollment(self, course_id: int, student_id: int, *, lock=False):
        return await self.fetch_one(
            """SELECT id, course_id, student_id FROM enrollments
               WHERE course_id=:course AND student_id=:student AND status='ACTIVE'"""
            + (" FOR UPDATE" if lock else ""),
            {"course": course_id, "student": student_id},
        )

    async def lesson(self, course_id: int, lesson_id: int):
        return await self.fetch_one(
            """SELECT l.id FROM lessons l JOIN modules m ON m.id=l.module_id
               WHERE l.id=:lesson AND m.course_id=:course AND l.deleted_at IS NULL
                 AND m.deleted_at IS NULL""",
            {"lesson": lesson_id, "course": course_id},
        )

    async def lesson_progress(self, enrollment_id: int, lesson_id: int, *, lock=False):
        return await self.fetch_one(
            """SELECT id, enrollment_id, lesson_id, status, last_position_seconds,
                      started_at, completed_at, updated_at
               FROM lesson_progress WHERE enrollment_id=:enrollment AND lesson_id=:lesson"""
            + (" FOR UPDATE" if lock else ""),
            {"enrollment": enrollment_id, "lesson": lesson_id},
        )

    async def completion_rule(self, course_id: int):
        return await self.fetch_one(
            """SELECT course_id, required_lesson_percent,
                      require_submitted_assignments, require_published_assignment_grades,
                      require_published_exam_grades, minimum_grade_percent, updated_by, updated_at
               FROM completion_rules WHERE course_id=:course FOR UPDATE""",
            {"course": course_id},
        )

    async def course_progress(self, enrollment_id: int):
        return await self.fetch_one(
            """SELECT enrollment_id, completed_lessons, total_lessons,
                      completed_assignments, total_assignments,
                      passed_assignments, total_exams, passed_exams,
                      progress_percent, completed_at, updated_at
               FROM course_progress WHERE enrollment_id=:enrollment""",
            {"enrollment": enrollment_id},
        )
