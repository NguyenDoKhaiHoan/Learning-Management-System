"""Scoped draft, publish and revision workflow with optimistic versions."""

import json
from decimal import Decimal

from fastapi import HTTPException

from src.modules.course.application.service import CourseService
from src.modules.gradebook.infrastructure.repository import GradeRepository
from src.modules.learning_progress_analytics.application.service import ProgressService
from src.modules.notification.application.events import NotificationEvents


class GradeService(CourseService):
    def __init__(self, connection, user, trace_id):
        super().__init__(connection, user, trace_id)
        self.grades = GradeRepository(connection)

    async def scope(self, course_id, enrollment_id):
        course = await self.authorize(course_id, write=True)
        if course["status"] == "ARCHIVED":
            raise HTTPException(409, "Archived course")
        enrollment = await self.repo.fetch_one(
            "SELECT * FROM enrollments WHERE id=:id AND course_id=:course FOR UPDATE",
            {"id": enrollment_id, "course": course_id},
        )
        if not enrollment:
            raise HTTPException(422, "Enrollment outside course")

    async def assessment(self, course_id, type, id):
        if type == "EXAM":
            sql = "SELECT * FROM exams WHERE id=:id AND course_id=:course FOR UPDATE"
        else:
            sql = """SELECT * FROM assignments WHERE id=:id AND course_id=:course
            AND deleted_at IS NULL FOR UPDATE"""
        row = await self.repo.fetch_one(sql, {"id": id, "course": course_id})
        if not row:
            raise HTTPException(422, "Assessment outside course")
        if row["status"] == "DRAFT":
            raise HTTPException(409, "Assessment not published")
        return row

    async def locked(self, id):
        row = await self.grades.fetch_one(
            """SELECT g.*,e.course_id FROM gradebook_entries g
            JOIN enrollments e ON e.id=g.enrollment_id WHERE g.id=:id""",
            {"id": id},
        )
        if not row:
            raise HTTPException(404)
        await self.scope(row["course_id"], row["enrollment_id"])
        await self.assessment(row["course_id"], row["assessment_type"], row["assessment_id"])
        grade = await self.grades.fetch_one(
            "SELECT * FROM gradebook_entries WHERE id=:id FOR UPDATE", {"id": id}
        )
        return grade | {"course_id": row["course_id"]}

    def items(self, body, max_score):
        items = [item.model_dump() for item in body.items]
        if sum((i["max_score"] for i in items), Decimal("0")) != max_score:
            raise HTTPException(422, "Item maximums must equal assessment maximum")
        return items, sum((i["score"] for i in items), Decimal("0"))

    async def create(self, course_id, body):
        await self.scope(course_id, body.enrollment_id)
        assessment = await self.assessment(course_id, body.assessment_type, body.assessment_id)
        values = {
            "source": body.source_id,
            "enrollment": body.enrollment_id,
            "assessment": body.assessment_id,
        }
        if body.assessment_type == "EXAM":
            source = await self.repo.fetch_one(
                """SELECT * FROM exam_attempts WHERE id=:source AND enrollment_id=:enrollment
                AND exam_id=:assessment AND status IN ('SUBMITTED','AUTO_SUBMITTED')
                AND graded_at IS NOT NULL FOR UPDATE""",
                values,
            )
        else:
            source = await self.repo.fetch_one(
                """SELECT * FROM assignment_submissions
                WHERE id=:source AND enrollment_id=:enrollment AND assignment_id=:assessment
                FOR UPDATE""",
                values,
            )
        if not source:
            raise HTTPException(422, "Source outside assessment/enrollment or not submitted")
        existing = await self.grades.fetch_one(
            """SELECT id FROM gradebook_entries WHERE enrollment_id=:enrollment
            AND assessment_type=:type AND assessment_id=:assessment FOR UPDATE""",
            values | {"type": body.assessment_type},
        )
        if existing:
            raise HTTPException(409, "Grade exists; edit the draft or revise the published grade")
        maximum = source["max_score"] if body.assessment_type == "EXAM" else assessment["max_score"]
        items, score = self.items(body, maximum)
        id = await self.grades.insert(
            """INSERT INTO gradebook_entries
            (enrollment_id,assessment_type,assessment_id,score,max_score,feedback,graded_by,
             source_attempt_id,source_submission_id)
            VALUES (:enrollment,:type,:assessment,:score,:max,:feedback,
                    :actor,:attempt,:submission)""",
            values
            | {
                "type": body.assessment_type,
                "score": score,
                "max": maximum,
                "feedback": body.feedback,
                "actor": int(self.user.id),
                "attempt": body.source_id if body.assessment_type == "EXAM" else None,
                "submission": body.source_id if body.assessment_type == "ASSIGNMENT" else None,
            },
        )
        await self.grades.replace_items(id, items)
        row = await self.grades.record(id, "DRAFT", int(self.user.id), self.trace_id)
        await self.connection.commit()
        return row

    async def refresh_completion(self, grade):
        await ProgressService(self.connection, self.user, self.trace_id).refresh_course(
            grade["course_id"], grade["enrollment_id"]
        )

    async def edit(self, id, body, revise=False):
        grade = await self.locked(id)
        if grade["version"] != body.expected_version:
            raise HTTPException(409, "Stale grade version; reload")
        required = "PUBLISHED" if revise else "DRAFT"
        if grade["status"] != required:
            raise HTTPException(409, "Invalid grade transition")
        items, score = self.items(body, grade["max_score"])
        await self.grades.execute(
            """UPDATE gradebook_entries SET score=:score,feedback=:feedback,graded_by=:actor,
            status='DRAFT',published_at=NULL,version=version+1 WHERE id=:id""",
            {"id": id, "score": score, "feedback": body.feedback, "actor": int(self.user.id)},
        )
        await self.grades.replace_items(id, items)
        row = await self.grades.record(
            id,
            "REVISE" if revise else "DRAFT",
            int(self.user.id),
            self.trace_id,
            body.reason if revise else None,
        )
        await self.refresh_completion(grade)
        await self.connection.commit()
        return row

    async def publish(self, id, body):
        grade = await self.locked(id)
        if grade["status"] == "PUBLISHED" and body.expected_version in {
            grade["version"],
            grade["version"] - 1,
        }:
            return await self.grades.detail(id)
        if grade["version"] != body.expected_version:
            raise HTTPException(409, "Stale grade version; reload")
        if grade["score"] is None:
            raise HTTPException(409, "Grade has no score")
        await self.grades.execute(
            """UPDATE gradebook_entries SET status='PUBLISHED',published_at=UTC_TIMESTAMP(6),
            version=version+1 WHERE id=:id""",
            {"id": id},
        )
        row = await self.grades.record(id, "PUBLISH", int(self.user.id), self.trace_id)
        await self.refresh_completion(grade)
        await NotificationEvents(self.connection).grade_published(
            grade["course_id"], grade["enrollment_id"], id
        )
        await self.connection.commit()
        return row

    async def history(self, id):
        await self.locked(id)
        rows = await self.grades.fetch_all(
            """SELECT version,action,actor_id,reason,snapshot,created_at FROM grade_history
            WHERE grade_id=:id ORDER BY version FOR UPDATE""",
            {"id": id},
        )
        for row in rows:
            row["snapshot"] = json.loads(row["snapshot"])
        return rows

    async def list(self, course_id, student=False):
        if student:
            if "STUDENT" not in self.user.roles:
                raise HTTPException(403)
            course = await self.repo.fetch_one(
                "SELECT status FROM courses WHERE id=:id AND deleted_at IS NULL FOR UPDATE",
                {"id": course_id},
            )
            enrollment = await self.repo.fetch_one(
                """SELECT id FROM enrollments WHERE course_id=:course AND student_id=:user
                AND status IN ('ACTIVE','COMPLETED') FOR UPDATE""",
                {"course": course_id, "user": int(self.user.id)},
            )
            if not course or course["status"] != "PUBLISHED" or not enrollment:
                raise HTTPException(403)
            rows = await self.grades.fetch_all(
                """SELECT id FROM gradebook_entries WHERE enrollment_id=:id
                AND status='PUBLISHED' ORDER BY id FOR UPDATE""",
                {"id": enrollment["id"]},
            )
        else:
            await self.authorize(course_id, write=True)
            rows = await self.grades.fetch_all(
                """SELECT g.id FROM gradebook_entries g JOIN enrollments e ON e.id=g.enrollment_id
                WHERE e.course_id=:id ORDER BY g.id FOR UPDATE""",
                {"id": course_id},
            )
        data = [await self.grades.detail(r["id"]) for r in rows]
        await self.connection.commit()
        return data
