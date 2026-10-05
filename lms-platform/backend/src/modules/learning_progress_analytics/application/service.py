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
        # All callers serialize on course -> enrollment before these current reads.
        # Locking reads also see commits made after authentication's SQL snapshot.
        params = {"course": course_id, "enrollment": enrollment_id}
        lessons = await self.repo.fetch_all(
            """SELECT l.id, lp.status FROM lessons l JOIN modules m ON m.id=l.module_id
            LEFT JOIN lesson_progress lp ON lp.lesson_id=l.id AND lp.enrollment_id=:enrollment
            WHERE m.course_id=:course AND m.deleted_at IS NULL AND l.deleted_at IS NULL
            FOR UPDATE""",
            params,
        )
        total = len(lessons)
        completed = sum(row["status"] == "COMPLETED" for row in lessons)
        rule = await self.repo.completion_rule(course_id)
        required = Decimal(rule["required_lesson_percent"]) if rule else Decimal("100")
        needs_assignments = bool(rule and rule["require_submitted_assignments"])
        needs_assignment_grades = bool(rule and rule["require_published_assignment_grades"])
        needs_exam_grades = bool(rule and rule["require_published_exam_grades"])
        minimum = Decimal(rule["minimum_grade_percent"]) if rule else Decimal("50")
        assignments = await self.repo.fetch_all(
            """SELECT id FROM assignments WHERE course_id=:course AND deleted_at IS NULL
            AND status IN ('PUBLISHED','CLOSED') FOR UPDATE""",
            params,
        )
        submissions = await self.repo.fetch_all(
            "SELECT assignment_id FROM assignment_submissions WHERE enrollment_id=:enrollment "
            "FOR UPDATE",
            params,
        )
        exams = await self.repo.fetch_all(
            "SELECT id FROM exams WHERE course_id=:course AND status IN ('PUBLISHED','CLOSED') "
            "FOR UPDATE",
            params,
        )
        grades = await self.repo.fetch_all(
            """SELECT assessment_type,assessment_id,score,max_score FROM gradebook_entries
            WHERE enrollment_id=:enrollment AND status='PUBLISHED' FOR UPDATE""",
            params,
        )
        passed = {
            (g["assessment_type"], g["assessment_id"])
            for g in grades
            if g["score"] is not None
            and g["max_score"] > 0
            and g["score"] * 100 >= minimum * g["max_score"]
        }
        submitted = {s["assignment_id"] for s in submissions}
        total_assignments = len(assignments)
        completed_assignments = sum(a["id"] in submitted for a in assignments)
        passed_assignments = sum(("ASSIGNMENT", a["id"]) in passed for a in assignments)
        total_exams = len(exams)
        passed_exams = sum(("EXAM", e["id"]) in passed for e in exams)
        # One assessment counts once even if both submission and grade gates are enabled.
        assignment_done = sum(
            (not needs_assignments or a["id"] in submitted)
            and (not needs_assignment_grades or ("ASSIGNMENT", a["id"]) in passed)
            for a in assignments
        )
        count_assignments = needs_assignments or needs_assignment_grades
        total_items = total + (total_assignments if count_assignments else 0)
        total_items += total_exams if needs_exam_grades else 0
        completed_items = completed + (assignment_done if count_assignments else 0)
        completed_items += passed_exams if needs_exam_grades else 0
        percent = (
            (Decimal(completed_items) * 100 / Decimal(total_items)).quantize(Decimal("0.01"))
            if total_items
            else Decimal("0")
        )
        lessons_done = total > 0 and Decimal(completed) * 100 >= required * total
        assignments_done = not count_assignments or assignment_done == total_assignments
        exams_done = not needs_exam_grades or passed_exams == total_exams
        is_complete = lessons_done and assignments_done and exams_done
        await self.repo.execute(
            """INSERT INTO course_progress
               (enrollment_id, completed_lessons, total_lessons,
                completed_assignments, total_assignments, passed_assignments,
                total_exams, passed_exams,
                progress_percent, completed_at)
               VALUES (:enrollment, :completed, :total,
                       :completed_assignments, :total_assignments, :passed_assignments,
                       :total_exams,
                       :passed_exams, :percent,
                       CASE WHEN :complete THEN UTC_TIMESTAMP(6) END)
               ON DUPLICATE KEY UPDATE completed_lessons=VALUES(completed_lessons),
                 total_lessons=VALUES(total_lessons),
                 completed_assignments=VALUES(completed_assignments),
                 total_assignments=VALUES(total_assignments),
                 passed_assignments=VALUES(passed_assignments), total_exams=VALUES(total_exams),
                 passed_exams=VALUES(passed_exams),
                 progress_percent=VALUES(progress_percent),
                 completed_at=CASE WHEN :complete
                   THEN COALESCE(completed_at, UTC_TIMESTAMP(6)) ELSE NULL END""",
            {
                "enrollment": enrollment_id,
                "completed": completed,
                "total": total,
                "completed_assignments": completed_assignments,
                "total_assignments": total_assignments,
                "passed_assignments": passed_assignments,
                "total_exams": total_exams,
                "passed_exams": passed_exams,
                "percent": percent,
                "complete": is_complete,
            },
        )
        return await self.repo.course_progress(enrollment_id)
