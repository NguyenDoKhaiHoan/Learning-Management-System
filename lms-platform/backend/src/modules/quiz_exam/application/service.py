"""Serialized exam policy and attempt operations."""

import json
import random
from datetime import timedelta

from fastapi import HTTPException

from src.modules.course.application.service import CourseService


class ExamService(CourseService):
    async def manager(self, course_id):
        row = await self.authorize(course_id, write=True)
        if row["status"] == "ARCHIVED":
            raise HTTPException(409, "Archived course")
        return row

    async def now(self):
        return (await self.repo.fetch_one("SELECT UTC_TIMESTAMP(6) now"))["now"]

    async def finish(self, action, resource, id):
        await self.audit(action, resource, id)
        await self.connection.commit()

    async def bank(self, id):
        row = await self.repo.fetch_one("SELECT * FROM question_banks WHERE id=:id", {"id": id})
        if not row:
            raise HTTPException(404)
        await self.manager(row["course_id"])
        return row

    async def exam(self, id, student=False):
        row = await self.repo.fetch_one("SELECT * FROM exams WHERE id=:id", {"id": id})
        if not row:
            raise HTTPException(404)
        enrollment = None
        if student:
            if "STUDENT" not in self.user.roles:
                raise HTTPException(403)
            course = await self.repo.fetch_one(
                "SELECT status FROM courses WHERE id=:id AND deleted_at IS NULL FOR UPDATE",
                {"id": row["course_id"]},
            )
            if not course or course["status"] != "PUBLISHED":
                raise HTTPException(403)
            enrollment = await self.repo.fetch_one(
                """SELECT * FROM enrollments WHERE course_id=:course
                   AND student_id=:user FOR UPDATE""",
                {"course": row["course_id"], "user": int(self.user.id)},
            )
            if not enrollment or enrollment["status"] != "ACTIVE":
                raise HTTPException(403)
        else:
            await self.manager(row["course_id"])
        row = await self.repo.fetch_one("SELECT * FROM exams WHERE id=:id FOR UPDATE", {"id": id})
        if not row or (student and row["status"] == "DRAFT"):
            raise HTTPException(404)
        return row, enrollment

    async def question(self, id):
        row = await self.repo.fetch_one(
            "SELECT * FROM questions WHERE id=:id FOR UPDATE", {"id": id}
        )
        if not row:
            raise HTTPException(404)
        row["options"] = await self.repo.fetch_all(
            """SELECT id,option_key,option_text,is_correct FROM question_options
               WHERE question_id=:id ORDER BY id""",
            {"id": id},
        )
        return row

    async def expire(self, attempt, now):
        if attempt["status"] == "IN_PROGRESS" and now >= attempt["expires_at"]:
            await self.repo.execute(
                """UPDATE exam_attempts SET status='AUTO_SUBMITTED',
                submitted_at=expires_at,server_version=server_version+1 WHERE id=:id""",
                {"id": attempt["id"]},
            )
            attempt.update(
                status="AUTO_SUBMITTED",
                submitted_at=attempt["expires_at"],
                server_version=attempt["server_version"] + 1,
            )
            await self.audit("attempt.expire", "exam_attempt", attempt["id"])

    async def eligibility(self, id):
        exam, enrollment = await self.exam(id, student=True)
        attempts = await self.repo.fetch_all(
            """SELECT * FROM exam_attempts
            WHERE exam_id=:id AND enrollment_id=:enrollment ORDER BY attempt_no FOR UPDATE""",
            {"id": id, "enrollment": enrollment["id"]},
        )
        now = await self.now()
        for attempt in attempts:
            await self.expire(attempt, now)
        active = next((a for a in attempts if a["status"] == "IN_PROGRESS"), None)
        reasons = []
        if exam["status"] != "PUBLISHED":
            reasons.append("NOT_PUBLISHED")
        if not exam["opens_at"] <= now < exam["due_at"]:
            reasons.append("OUTSIDE_WINDOW")
        if len(attempts) >= exam["max_attempts"]:
            reasons.append("ATTEMPTS_EXHAUSTED")
        if active:
            reasons.append("ACTIVE_ATTEMPT")
        data = {
            "eligible": not reasons,
            "reasons": reasons,
            "attempts_used": len(attempts),
            "max_attempts": exam["max_attempts"],
            "active_attempt_id": str(active["id"]) if active else None,
            "can_resume": bool(active and exam["allow_resume"] and exam["status"] == "PUBLISHED"),
            "server_time": now,
        }
        return exam, enrollment, attempts, data

    async def start(self, id):
        exam, enrollment, attempts, eligibility = await self.eligibility(id)
        if not eligibility["eligible"]:
            await self.connection.commit()
            raise HTTPException(409, ",".join(eligibility["reasons"]))
        questions = await self.repo.fetch_all(
            "SELECT * FROM exam_questions WHERE exam_id=:id ORDER BY position", {"id": id}
        )
        snapshot = []
        for question in questions:
            item = await self.question(question["question_id"])
            item["points"] = float(question["points"])
            snapshot.append(
                {k: item[k] for k in ("id", "prompt", "question_type", "points", "options")}
            )
        if not snapshot:
            raise HTTPException(409, "Empty exam")
        if exam["shuffle_questions"]:
            random.SystemRandom().shuffle(snapshot)
        now = await self.now()
        expires = min(now + timedelta(seconds=exam["duration_seconds"]), exam["due_at"])
        id = await self.repo.insert(
            """INSERT INTO exam_attempts
            (exam_id,enrollment_id,attempt_no,started_at,expires_at,max_score,question_snapshot)
            VALUES (:exam,:enrollment,:number,:now,:expires,:score,:snapshot)""",
            {
                "exam": id,
                "enrollment": enrollment["id"],
                "number": len(attempts) + 1,
                "now": now,
                "expires": expires,
                "score": sum(q["points"] for q in snapshot),
                "snapshot": json.dumps(snapshot),
            },
        )
        await self.finish("attempt.start", "exam_attempt", id)
        return await self.view(id, resume=False)

    async def attempt(self, id):
        row = await self.repo.fetch_one("SELECT * FROM exam_attempts WHERE id=:id", {"id": id})
        if not row:
            raise HTTPException(404)
        exam, enrollment = await self.exam(row["exam_id"], student=True)
        if row["enrollment_id"] != enrollment["id"]:
            raise HTTPException(404)
        row = await self.repo.fetch_one(
            "SELECT * FROM exam_attempts WHERE id=:id FOR UPDATE", {"id": id}
        )
        await self.expire(row, await self.now())
        return row, exam

    async def view(self, id, resume=True):
        row, exam = await self.attempt(id)
        if (
            resume
            and row["status"] == "IN_PROGRESS"
            and (not exam["allow_resume"] or exam["status"] != "PUBLISHED")
        ):
            raise HTTPException(409, "Resume disabled")
        snapshot = json.loads(row.pop("question_snapshot") or "[]")
        for question in snapshot:
            for option in question["options"]:
                option.pop("is_correct", None)
        row["questions"] = snapshot
        row["answers"] = await self.repo.fetch_all(
            """SELECT question_id,selected_option_ids
            FROM exam_answers WHERE attempt_id=:id""",
            {"id": id},
        )
        for answer in row["answers"]:
            answer["selected_option_ids"] = json.loads(answer["selected_option_ids"] or "[]")
        row["server_time"] = await self.now()
        row["remaining_seconds"] = max(
            0, int((row["expires_at"] - row["server_time"]).total_seconds())
        )
        if row["status"] != "IN_PROGRESS":
            row["remaining_seconds"] = 0
        row.pop("score", None)
        await self.connection.commit()
        return row

    async def save(self, id, question_id, body):
        row, exam = await self.attempt(id)
        if row["status"] != "IN_PROGRESS" or exam["status"] != "PUBLISHED":
            await self.connection.commit()
            raise HTTPException(409, "Attempt closed")
        if row["server_version"] != body.expected_version:
            raise HTTPException(409, "Stale version; reload attempt")
        snapshot = json.loads(row["question_snapshot"] or "[]")
        question = next((q for q in snapshot if q["id"] == question_id), None)
        if not question:
            raise HTTPException(422, "Question outside attempt")
        options = body.selected_option_ids
        if (
            len(options) != len(set(options))
            or not set(options).issubset({o["id"] for o in question["options"]})
            or (question["question_type"] != "MULTIPLE" and len(options) > 1)
        ):
            raise HTTPException(422, "Invalid options")
        now = await self.now()
        await self.repo.execute(
            """INSERT INTO exam_answers
            (attempt_id,question_id,selected_option_ids,answered_at)
            VALUES (:id,:q,:options,:now) ON DUPLICATE KEY UPDATE
            selected_option_ids=:options,answered_at=:now""",
            {"id": id, "q": question_id, "options": json.dumps(options), "now": now},
        )
        await self.repo.execute(
            """UPDATE exam_attempts SET server_version=server_version+1
            WHERE id=:id""",
            {"id": id},
        )
        await self.finish("attempt.autosave", "exam_attempt", id)
        return {"id": str(id), "server_version": row["server_version"] + 1, "saved_at": now}

    async def submit(self, id):
        row, _ = await self.attempt(id)
        if row["status"] == "IN_PROGRESS":
            await self.repo.execute(
                """UPDATE exam_attempts SET status='SUBMITTED',
                submitted_at=UTC_TIMESTAMP(6),server_version=server_version+1 WHERE id=:id""",
                {"id": id},
            )
            await self.audit("attempt.submit", "exam_attempt", id)
        await self.connection.commit()
        return await self.view(id, resume=False)
