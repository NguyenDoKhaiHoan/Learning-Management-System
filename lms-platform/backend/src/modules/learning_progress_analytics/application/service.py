"""Monotonic lesson progress and transactionally refreshed course progress."""

from decimal import Decimal

from fastapi import HTTPException

from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.course.application.service import CourseService
from src.modules.learning_progress_analytics.domain.enums import LessonProgressStatus
from src.modules.learning_progress_analytics.infrastructure.repository import ProgressRepository


class ProgressService:
    def __init__(self, connection, user, trace_id):
        self.connection = connection
        self.user = user
        self.trace_id = trace_id
        self.repo = ProgressRepository(connection)

    async def learner_context(self, course_id: int, *, lock=False):
        if lock:
            course = await self.repo.fetch_one(
                "SELECT status FROM courses WHERE id=:id AND deleted_at IS NULL FOR UPDATE",
                {"id": course_id},
            )
            if course is None:
                raise HTTPException(404)
            if course["status"] != "PUBLISHED":
                raise HTTPException(403)
        else:
            await CourseService(self.connection, self.user, self.trace_id).authorize(course_id)
        enrollment = await self.repo.active_enrollment(course_id, int(self.user.id), lock=lock)
        if enrollment is None:
            raise HTTPException(403)
        return enrollment

    async def update_lesson(self, course_id, lesson_id, status, position):
        enrollment = await self.learner_context(course_id, lock=True)
        if await self.repo.lesson(course_id, lesson_id) is None:
            raise HTTPException(404)
        current = await self.repo.lesson_progress(enrollment["id"], lesson_id, lock=True)
        old = (
            LessonProgressStatus(current["status"]) if current else LessonProgressStatus.NOT_STARTED
        )
        target = LessonProgressStatus(status)
        allowed = {
            LessonProgressStatus.NOT_STARTED: {
                LessonProgressStatus.IN_PROGRESS,
                LessonProgressStatus.COMPLETED,
            },
            LessonProgressStatus.IN_PROGRESS: {
                LessonProgressStatus.IN_PROGRESS,
                LessonProgressStatus.COMPLETED,
            },
            LessonProgressStatus.COMPLETED: {LessonProgressStatus.COMPLETED},
        }
        if target not in allowed[old]:
            raise HTTPException(409, "Lesson progress cannot move backwards")
        if current and position < current["last_position_seconds"]:
            raise HTTPException(409, "Lesson position cannot move backwards")
        params = {
            "enrollment": enrollment["id"],
            "lesson": lesson_id,
            "status": target.value,
            "position": position,
        }
        if current is None:
            await self.repo.execute(
                """INSERT INTO lesson_progress
                   (enrollment_id, lesson_id, status, last_position_seconds,
                    started_at, completed_at)
                   VALUES (:enrollment, :lesson, :status, :position, UTC_TIMESTAMP(6),
                           CASE WHEN :status='COMPLETED' THEN UTC_TIMESTAMP(6) END)""",
                params,
            )
        else:
            await self.repo.execute(
                """UPDATE lesson_progress SET status=:status,
                   last_position_seconds=:position,
                   completed_at=CASE
                     WHEN :status='COMPLETED' THEN COALESCE(completed_at, UTC_TIMESTAMP(6))
                     ELSE NULL END
                   WHERE enrollment_id=:enrollment AND lesson_id=:lesson""",
                params,
            )
        course = await self.refresh_course(course_id, enrollment["id"])
        await AuditRepository(self.connection).append_log(
            actor_id=int(self.user.id),
            action="lesson_progress." + target.value.lower(),
            resource="lesson",
            resource_id=str(lesson_id),
            trace_id=self.trace_id,
            details={"course_id": str(course_id)},
        )
        await self.connection.commit()
        lesson = await self.repo.lesson_progress(enrollment["id"], lesson_id)
        return lesson, course

    async def refresh_course(self, course_id: int, enrollment_id: int):
        counts = await self.repo.fetch_one(
            """SELECT COUNT(*) AS total_lessons,
                      SUM(CASE WHEN lp.status='COMPLETED' THEN 1 ELSE 0 END) AS completed_lessons
               FROM lessons l JOIN modules m ON m.id=l.module_id
               LEFT JOIN lesson_progress lp ON lp.lesson_id=l.id
                    AND lp.enrollment_id=:enrollment
               WHERE m.course_id=:course AND m.deleted_at IS NULL AND l.deleted_at IS NULL""",
            {"course": course_id, "enrollment": enrollment_id},
        )
        total = int(counts["total_lessons"] or 0)
        completed = int(counts["completed_lessons"] or 0)
        rule = await self.repo.completion_rule(course_id)
        required = Decimal(rule["required_lesson_percent"]) if rule else Decimal("100.00")
        needs_assignments = bool(rule["require_submitted_assignments"]) if rule else False
        assignment_counts = await self.repo.fetch_one(
            """SELECT COUNT(*) AS total_assignments,
                      SUM(CASE WHEN EXISTS (
                        SELECT 1 FROM assignment_submissions s
                        WHERE s.assignment_id=a.id AND s.enrollment_id=:enrollment
                      ) THEN 1 ELSE 0 END) AS completed_assignments
               FROM assignments a WHERE a.course_id=:course AND a.deleted_at IS NULL
                 AND a.status IN ('PUBLISHED','CLOSED')""",
            {"course": course_id, "enrollment": enrollment_id},
        )
        total_assignments = int(assignment_counts["total_assignments"] or 0)
        completed_assignments = int(assignment_counts["completed_assignments"] or 0)
        total_items = total + (total_assignments if needs_assignments else 0)
        completed_items = completed + (completed_assignments if needs_assignments else 0)
        percent = (
            (Decimal(completed_items) * 100 / Decimal(total_items)).quantize(Decimal("0.01"))
            if total_items
            else Decimal("0.00")
        )
        # The rule uses exact ratios; rounding the displayed percent must not mark
        # a learner complete when the underlying lesson fraction is still below it.
        lessons_done = total > 0 and Decimal(completed) * 100 >= required * total
        assignments_done = not needs_assignments or completed_assignments == total_assignments
        is_complete = lessons_done and assignments_done
        await self.repo.execute(
            """INSERT INTO course_progress
               (enrollment_id, completed_lessons, total_lessons,
                completed_assignments, total_assignments, progress_percent, completed_at)
               VALUES (:enrollment, :completed, :total,
                       :completed_assignments, :total_assignments, :percent,
                       CASE WHEN :complete THEN UTC_TIMESTAMP(6) END)
               ON DUPLICATE KEY UPDATE completed_lessons=VALUES(completed_lessons),
                 total_lessons=VALUES(total_lessons),
                 completed_assignments=VALUES(completed_assignments),
                 total_assignments=VALUES(total_assignments),
                 progress_percent=VALUES(progress_percent),
                 completed_at=CASE WHEN :complete
                   THEN COALESCE(completed_at, UTC_TIMESTAMP(6)) ELSE NULL END""",
            {
                "enrollment": enrollment_id,
                "completed": completed,
                "total": total,
                "completed_assignments": completed_assignments,
                "total_assignments": total_assignments,
                "percent": percent,
                "complete": is_complete,
            },
        )
        return await self.repo.course_progress(enrollment_id)
