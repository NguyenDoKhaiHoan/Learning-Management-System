"""Published assignment and exam gates, revision and transactional completion."""

from decimal import Decimal

import pytest
from sqlalchemy import text

from src.modules.audit_security.infrastructure.repository import AuditRepository
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week3_assignments import assignment_body
from tests.integration.test_week4_exams import setup_exam

pytestmark = pytest.mark.integration


async def test_exam_assignment_publication_completion_and_revision(api, monkeypatch):
    call, engine, cid, _, q, eid, _ = await setup_exam(api)
    await call("POST", f"/courses/{cid}/status", json={"status": "DRAFT"})
    rule = {
        "required_lesson_percent": 100,
        "require_submitted_assignments": True,
        "require_published_assignment_grades": True,
        "require_published_exam_grades": True,
        "minimum_grade_percent": 80,
    }
    await call("PUT", f"/courses/{cid}/completion-rule", json=rule)
    await call("PUT", f"/courses/{cid}/completion-rule", actor="student", json=rule, expected=403)
    await call(
        "PUT",
        f"/courses/{cid}/completion-rule",
        json=rule | {"minimum_grade_percent": 101},
        expected=422,
    )
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    modules = await call("GET", f"/courses/{cid}/modules", actor="student")
    lesson = modules[0]["lessons"][0]["id"]
    await call(
        "PUT",
        f"/courses/{cid}/lessons/{lesson}/progress",
        actor="student",
        json={"status": "COMPLETED"},
    )
    base = f"/courses/{cid}/assignments"
    assignment = await call("POST", base, expected=201, json=assignment_body())
    aid = assignment["id"]
    await call("POST", f"{base}/{aid}/status", json={"status": "PUBLISHED"})
    sub = await call(
        "POST",
        f"{base}/{aid}/submissions",
        actor="student",
        expected=201,
        json={"answer_text": "My answer"},
        headers={"Idempotency-Key": "completion"},
    )
    progress_path = f"/courses/{cid}/progress/me"
    enrollment = (await call("GET", progress_path, actor="student"))["enrollment_id"]
    grade = await call(
        "POST",
        f"/courses/{cid}/grades",
        expected=201,
        json={
            "enrollment_id": enrollment,
            "assessment_type": "ASSIGNMENT",
            "assessment_id": aid,
            "source_id": sub["id"],
            "items": [{"item_key": "overall", "label": "Essay", "score": 80, "max_score": 100}],
        },
    )
    await call("POST", f"/exams/{eid}/publish")
    attempt = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    await call(
        "PUT",
        f"/attempts/{attempt['id']}/answers/{q['id']}",
        actor="student",
        json={"selected_option_ids": [q["options"][0]["id"]], "expected_version": 0},
    )
    await call("POST", f"/attempts/{attempt['id']}/submit", actor="student")
    progress = await call("GET", progress_path, actor="student")
    assert progress["completed_at"] is None and progress["passed_exams"] == 0
    assert await call("GET", f"/courses/{cid}/grades/me", actor="student") == []
    exam_grade = next(
        g for g in await call("GET", f"/courses/{cid}/grades") if g["assessment_type"] == "EXAM"
    )
    await call("POST", f"/grades/{exam_grade['id']}/publish", json={"expected_version": 1})
    assert (await call("GET", progress_path, actor="student"))["completed_at"] is None

    original = AuditRepository.append_log

    async def fail(self, **kwargs):
        if kwargs["action"] == "grade.publish":
            raise RuntimeError("audit unavailable")
        return await original(self, **kwargs)

    monkeypatch.setattr(AuditRepository, "append_log", fail)
    with pytest.raises(RuntimeError):
        await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    monkeypatch.setattr(AuditRepository, "append_log", original)
    assert len(await call("GET", f"/courses/{cid}/grades/me", actor="student")) == 1
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    async with engine.connect() as conn:
        persisted = (await conn.execute(text("SELECT * FROM course_progress"))).mappings().one()
        assert persisted["completed_at"] and persisted["progress_percent"] == Decimal("100")
    progress = await call("GET", progress_path, actor="student")
    assert progress["passed_assignments"] == progress["passed_exams"] == 1
    assert len(await call("GET", f"/courses/{cid}/grades/me", actor="student")) == 2
    await call(
        "POST",
        f"/grades/{grade['id']}/revise",
        json={
            "expected_version": 2,
            "reason": "Rubric correction",
            "items": [{"item_key": "overall", "label": "Essay", "score": 79.99, "max_score": 100}],
        },
    )
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT completed_at FROM course_progress")) is None
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 3})
    assert (await call("GET", progress_path, actor="student"))["completed_at"] is None
    await call("GET", progress_path, actor="other", expected=403)
