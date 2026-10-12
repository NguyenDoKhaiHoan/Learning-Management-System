"""Untrusted client signals create review flags, never grading decisions."""

from fastapi import HTTPException

from src.modules.course.application.service import CourseService
from src.modules.quiz_exam.application.service import ExamService


def public_event(row):
    for key in ("id", "attempt_id", "reviewed_by", "student_id", "exam_id"):
        if row.get(key) is not None:
            row[key] = str(row[key])
    return row


def event_receipt(row):
    # Students receive ingestion receipts, not the manager's internal review notes.
    return {
        key: str(row[key]) if key in {"id", "attempt_id"} else row[key]
        for key in ("id", "attempt_id", "client_event_id", "event_type", "created_at")
    }


class AttemptEvents(CourseService):
    async def record(self, attempt_id, body):
        exam_service = ExamService(self.connection, self.user, self.trace_id)
        attempt, exam = await exam_service.attempt(attempt_id)
        existing = await self.repo.fetch_one(
            "SELECT * FROM attempt_events WHERE attempt_id=:attempt AND client_event_id=:client "
            "FOR UPDATE",
            {"attempt": attempt_id, "client": str(body.client_event_id)},
        )
        if existing:
            if existing["event_type"] != body.event_type:
                raise HTTPException(409, "Event identifier reused for different signal")
            await self.connection.commit()
            return event_receipt(existing)
        if attempt["status"] != "IN_PROGRESS" or exam["status"] != "PUBLISHED":
            await self.connection.commit()  # Preserve server-side deadline finalization.
            raise HTTPException(409, "Attempt closed")
        count = await self.repo.fetch_one(
            "SELECT COUNT(*) total FROM attempt_events WHERE attempt_id=:id FOR UPDATE",
            {"id": attempt_id},
        )
        if count["total"] >= 200:
            raise HTTPException(409, "Attempt telemetry limit reached")
        id = await self.repo.insert(
            """INSERT INTO attempt_events(attempt_id,client_event_id,event_type,trace_id)
            VALUES (:attempt,:client,:type,:trace)""",
            {
                "attempt": attempt_id,
                "client": str(body.client_event_id),
                "type": body.event_type,
                "trace": self.trace_id,
            },
        )
        await self.audit(
            "attempt.event",
            "attempt_event",
            id,
            details={"attempt_id": str(attempt_id), "event_type": body.event_type},
        )
        row = await self.repo.fetch_one("SELECT * FROM attempt_events WHERE id=:id", {"id": id})
        await self.connection.commit()
        return event_receipt(row)

    async def list(self, course_id, status, limit, offset):
        await self.authorize(course_id, write=True)
        params = {"course": course_id, "status": status, "limit": limit, "offset": offset}
        source = """FROM attempt_events v JOIN exam_attempts a ON a.id=v.attempt_id
            JOIN exams x ON x.id=a.exam_id JOIN enrollments e ON e.id=a.enrollment_id
            WHERE x.course_id=:course AND (:status IS NULL OR v.review_status=:status)"""
        count = await self.repo.fetch_one("SELECT COUNT(*) total " + source, params)
        rows = await self.repo.fetch_all(
            "SELECT v.*,e.student_id,x.id exam_id,x.title exam_title "
            + source
            + " ORDER BY v.created_at DESC,v.id DESC LIMIT :limit OFFSET :offset",
            params,
        )
        return {
            "items": [public_event(row) for row in rows],
            "total": count["total"],
            "limit": limit,
            "offset": offset,
        }

    async def review(self, course_id, event_id, body):
        await self.authorize(course_id, write=True)
        row = await self.repo.fetch_one(
            """SELECT v.* FROM attempt_events v JOIN exam_attempts a ON a.id=v.attempt_id
            JOIN exams x ON x.id=a.exam_id WHERE v.id=:id AND x.course_id=:course FOR UPDATE""",
            {"id": event_id, "course": course_id},
        )
        if not row:
            raise HTTPException(404)
        if row["version"] != body.expected_version or row["review_status"] != "PENDING":
            raise HTTPException(409, "Review has changed")
        await self.repo.execute(
            """UPDATE attempt_events SET review_status=:status,review_note=:note,
            reviewed_by=:actor,reviewed_at=UTC_TIMESTAMP(6),version=version+1 WHERE id=:id""",
            {"status": body.status, "note": body.note, "actor": int(self.user.id), "id": event_id},
        )
        await self.audit(
            "security.review",
            "attempt_event",
            event_id,
            details={
                "previous_status": "PENDING",
                "status": body.status,
                "note": body.note,
                "attempt_id": str(row["attempt_id"]),
                "version": row["version"] + 1,
            },
        )
        result = await self.repo.fetch_one(
            "SELECT * FROM attempt_events WHERE id=:id", {"id": event_id}
        )
        await self.connection.commit()
        return public_event(result)
