"""Deterministic snapshot grading and a single atomic close operation."""

import json
from decimal import Decimal

from src.core.database.sql import SqlRepository
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.gradebook.infrastructure.repository import GradeRepository


class AttemptGrader:
    def __init__(self, connection, actor_id=None, trace_id="exam-expiry-worker"):
        self.repo = SqlRepository(connection)
        self.grades = GradeRepository(connection)
        self.actor_id = actor_id
        self.trace_id = trace_id

    async def finalize(self, attempt, *, automatic=False):
        # Caller locks course -> enrollment -> exam -> attempt before entering.
        if attempt["status"] == "IN_PROGRESS":
            status = "AUTO_SUBMITTED" if automatic else "SUBMITTED"
            await self.repo.execute(
                """UPDATE exam_attempts SET status=:status,
                submitted_at=IF(:automatic,expires_at,UTC_TIMESTAMP(6)),
                server_version=server_version+1 WHERE id=:id""",
                {"id": attempt["id"], "status": status, "automatic": automatic},
            )
            attempt.update(status=status, server_version=attempt["server_version"] + 1)
            await AuditRepository(self.repo.connection).append_log(
                actor_id=self.actor_id,
                action="attempt.expire" if automatic else "attempt.submit",
                resource="exam_attempt",
                resource_id=str(attempt["id"]),
                trace_id=self.trace_id,
            )
        if attempt["status"] not in {"SUBMITTED", "AUTO_SUBMITTED"} or attempt["graded_at"]:
            return
        snapshot = json.loads(attempt["question_snapshot"] or "[]")
        if not snapshot:
            # Legacy attempts without a key must never silently receive an invented score.
            raise ValueError("Attempt has no grading snapshot")
        answers = await self.repo.fetch_all(
            """SELECT question_id,selected_option_ids FROM exam_answers
            WHERE attempt_id=:id FOR UPDATE""",
            {"id": attempt["id"]},
        )
        selected = {
            a["question_id"]: set(json.loads(a["selected_option_ids"] or "[]")) for a in answers
        }
        items = []
        for question in snapshot:
            key = {o["id"] for o in question["options"] if o["is_correct"]}
            correct = selected.get(question["id"], set()) == key
            points = Decimal(str(question["points"]))
            score = points if correct else Decimal("0")
            items.append(
                {
                    "item_key": str(question["id"]),
                    "label": question["prompt"],
                    "score": score,
                    "max_score": points,
                }
            )
            await self.repo.execute(
                """INSERT INTO exam_answers
                (attempt_id,question_id,selected_option_ids,is_correct,points_awarded)
                VALUES (:id,:q,'[]',:correct,:score) ON DUPLICATE KEY UPDATE
                is_correct=:correct,points_awarded=:score""",
                {"id": attempt["id"], "q": question["id"], "correct": correct, "score": score},
            )
        score = sum((i["score"] for i in items), Decimal("0"))
        await self.repo.execute(
            "UPDATE exam_attempts SET score=:score,graded_at=UTC_TIMESTAMP(6) WHERE id=:id",
            {"id": attempt["id"], "score": score},
        )
        attempt.update(score=score, graded_at=True)
        grade = await self.grades.fetch_one(
            """SELECT * FROM gradebook_entries WHERE enrollment_id=:enrollment
            AND assessment_type='EXAM' AND assessment_id=:exam FOR UPDATE""",
            {"enrollment": attempt["enrollment_id"], "exam": attempt["exam_id"]},
        )
        # Best attempt wins while the grade is an untouched automatic draft.
        # Instructor edits and published grades are never overwritten by a later attempt.
        if grade and (
            grade["status"] != "DRAFT"
            or grade["graded_by"] is not None
            or (grade["score"] is not None and grade["score"] >= score)
        ):
            return
        values = {"score": score, "max": attempt["max_score"], "attempt": attempt["id"]}
        if grade:
            id = grade["id"]
            await self.grades.execute(
                """UPDATE gradebook_entries SET score=:score,max_score=:max,
                source_attempt_id=:attempt,version=version+1 WHERE id=:id""",
                values | {"id": id},
            )
        else:
            id = await self.grades.insert(
                """INSERT INTO gradebook_entries
                (enrollment_id,assessment_type,assessment_id,score,max_score,source_attempt_id)
                VALUES (:enrollment,'EXAM',:exam,:score,:max,:attempt)""",
                values | {"enrollment": attempt["enrollment_id"], "exam": attempt["exam_id"]},
            )
        await self.grades.replace_items(id, items)
        await self.grades.record(id, "AUTO_GRADE", None, self.trace_id)
