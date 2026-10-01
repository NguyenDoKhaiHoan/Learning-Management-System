"""Real MySQL assessment journeys, boundaries, concurrency and resume policy."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_content, new_course

pytestmark = pytest.mark.integration


async def setup_exam(api, *, resume=True, blueprint=False):
    call, engine, users, _, _ = api
    course = await new_course(call)
    cid = course["id"]
    await new_content(call, cid)
    bank = await call("POST", f"/courses/{cid}/question-banks", expected=201, json={"name": "Bank"})
    bid = bank["id"]
    category = await call(
        "POST", f"/question-banks/{bid}/categories", expected=201, json={"name": "Algebra"}
    )
    qbody = {
        "question_type": "SINGLE",
        "prompt": "1+1?",
        "category_id": int(category["id"]),
        "difficulty": "EASY",
        "options": [{"key": "A", "text": "2", "is_correct": True}, {"key": "B", "text": "3"}],
    }
    q = await call("POST", f"/question-banks/{bid}/questions", expected=201, json=qbody)
    now = datetime.now(UTC)
    body = {
        "title": "Exam",
        "opens_at": (now - timedelta(minutes=1)).isoformat(),
        "due_at": (now + timedelta(hours=1)).isoformat(),
        "duration_seconds": 600,
        "allow_resume": resume,
        "max_attempts": 2,
        "questions": [{"question_id": q["id"], "position": 1, "points": 10}],
    }
    if blueprint:
        body.pop("questions")
        body["blueprint"] = [
            {
                "bank_id": int(bid),
                "category_id": int(category["id"]),
                "difficulty": "EASY",
                "question_type": "SINGLE",
                "question_count": 1,
                "points_each": 10,
            }
        ]
    exam = await call("POST", f"/courses/{cid}/exams", expected=201, json=body)
    eid = exam["id"]
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    async with engine.begin() as conn:
        await conn.execute(
            text("""INSERT INTO enrollments(student_id,course_id,status)
            VALUES (:student,:course,'ACTIVE')"""),
            {"student": users["student"], "course": cid},
        )
    return call, engine, cid, bid, q, eid, body


async def test_exam_blueprint_crud_and_boundaries(api):
    call, _, cid, bid, q, eid, body = await setup_exam(api, blueprint=True)
    await call("GET", f"/exams/{eid}", actor="other", expected=403)
    await call("GET", f"/question-banks/{bid}/questions", actor="student", expected=403)
    assert len(await call("GET", f"/question-banks/{bid}/questions?difficulty=EASY")) == 1
    assert not await call("GET", f"/question-banks/{bid}/questions?difficulty=HARD")
    await call("PUT", f"/courses/{cid}/exams/{eid}", json=body | {"title": "Edited"})
    assert (await call("GET", f"/exams/{eid}"))["title"] == "Edited"
    draft = await call("POST", f"/courses/{cid}/exams", expected=201, json=body)
    await call("DELETE", f"/exams/{draft['id']}")
    await call("GET", f"/exams/{draft['id']}", expected=404)
    await call("POST", f"/exams/{eid}/publish")
    detail = await call("GET", f"/exams/{eid}")
    assert detail["questions"][0]["question_id"] == q["id"]
    await call("POST", f"/exams/{eid}/publish", expected=409)
    await call("DELETE", f"/exams/{eid}", expected=409)
    await call("PUT", f"/courses/{cid}/exams/{eid}", json=body, expected=409)
    assert (await call("GET", f"/exams/{eid}/eligibility", actor="student"))["eligible"]


async def test_autosave_resume_submission_and_timer(api):
    call, engine, _, _, q, eid, _ = await setup_exam(api)
    await call("POST", f"/exams/{eid}/publish")
    a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    aid = a["id"]
    assert 0 < a["remaining_seconds"] <= 600
    assert "is_correct" not in str(a) and "explanation" not in str(a)
    answer = {"selected_option_ids": [q["options"][0]["id"]], "expected_version": 0}
    await call("PUT", f"/attempts/{aid}/answers/{q['id']}", actor="student", json=answer)
    await call(
        "PUT", f"/attempts/{aid}/answers/{q['id']}", actor="student", json=answer, expected=409
    )
    await call(
        "PUT",
        f"/attempts/{aid}/answers/99999",
        actor="student",
        json=answer | {"expected_version": 1},
        expected=422,
    )
    resumed = await call("GET", f"/attempts/{aid}", actor="student")
    assert resumed["answers"][0]["selected_option_ids"] == answer["selected_option_ids"]
    assert resumed["expires_at"] == a["expires_at"] and resumed["server_version"] == 1
    first = await call("POST", f"/attempts/{aid}/submit", actor="student")
    assert first["status"] == "SUBMITTED"
    again = await call("POST", f"/attempts/{aid}/submit", actor="student")
    assert again["server_version"] == first["server_version"]
    await call(
        "PUT",
        f"/attempts/{aid}/answers/{q['id']}",
        actor="student",
        json=answer | {"expected_version": 2},
        expected=409,
    )
    a2 = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    async with engine.begin() as conn:
        await conn.execute(
            text("""UPDATE exam_attempts
            SET started_at=UTC_TIMESTAMP(6)-INTERVAL 10 MINUTE,
                expires_at=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id=:id"""),
            {"id": a2["id"]},
        )
    expired = await call("GET", f"/attempts/{a2['id']}", actor="student")
    assert expired["status"] == "AUTO_SUBMITTED" and expired["remaining_seconds"] == 0
    await call("POST", f"/exams/{eid}/attempts", actor="student", expected=409)


async def test_concurrent_start_and_save_and_suspension(api):
    call, engine, cid, _, q, eid, _ = await setup_exam(api)
    await call("POST", f"/exams/{eid}/publish")
    _, _, users, tokens, client = api
    headers = {"Authorization": "Bearer " + tokens["student"]["access_token"]}
    responses = await asyncio.gather(
        *[client.post(f"/api/v1/exams/{eid}/attempts", headers=headers) for _ in range(2)]
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    aid = next(r.json()["data"]["id"] for r in responses if r.status_code == 201)
    responses = await asyncio.gather(
        *[
            client.put(
                f"/api/v1/attempts/{aid}/answers/{q['id']}",
                headers=headers,
                json={"selected_option_ids": [q["options"][0]["id"]], "expected_version": 0},
            )
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE enrollments SET status='SUSPENDED' WHERE course_id=:id"), {"id": cid}
        )
    await call("GET", f"/attempts/{aid}", actor="student", expected=403)
    await call("POST", f"/attempts/{aid}/submit", actor="student", expected=403)
    await call("GET", f"/attempts/{aid}", actor="other", expected=403)


async def test_resume_disabled_and_invalid_blueprint(api):
    call, _, cid, bid, _, eid, body = await setup_exam(api, resume=False)
    await call("POST", f"/exams/{eid}/publish")
    a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    await call("GET", f"/attempts/{a['id']}", actor="student", expected=409)
    await call("POST", f"/attempts/{a['id']}/submit", actor="student")
    invalid = body | {
        "questions": [],
        "blueprint": [
            {
                "bank_id": int(bid),
                "difficulty": "HARD",
                "question_type": "SINGLE",
                "question_count": 5,
                "points_each": 1,
            }
        ],
    }
    draft = await call("POST", f"/courses/{cid}/exams", expected=201, json=invalid)
    await call("POST", f"/exams/{draft['id']}/publish", expected=409)
    detail = await call("GET", f"/exams/{draft['id']}")
    assert detail["status"] == "DRAFT" and not detail["questions"]


async def test_validation_cross_course_and_snapshot(api):
    call, engine, cid, bid, q, eid, body = await setup_exam(api)
    other = await new_course(call, code="SECOND")
    await call("POST", f"/courses/{other['id']}/exams", json=body, expected=422)
    invalid_question = {
        "question_type": "SINGLE",
        "prompt": "Invalid",
        "options": [{"key": "A", "text": "A"}, {"key": "B", "text": "B"}],
    }
    await call("POST", f"/question-banks/{bid}/questions", json=invalid_question, expected=422)
    invalid_question["options"][0]["is_correct"] = True
    invalid_question["category_id"] = 999999
    await call("POST", f"/question-banks/{bid}/questions", json=invalid_question, expected=422)
    await call(
        "POST",
        f"/courses/{cid}/exams",
        json=body | {"opens_at": "2026-01-01T00:00:00"},
        expected=422,
    )
    await call("POST", f"/exams/{eid}/publish")
    a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE questions SET prompt='Changed later' WHERE id=:id"), {"id": q["id"]}
        )
    resumed = await call("GET", f"/attempts/{a['id']}", actor="student")
    assert resumed["questions"][0]["prompt"] == "1+1?"
    await call(
        "PUT",
        f"/attempts/{a['id']}/answers/{q['id']}",
        actor="student",
        json={"expected_version": 0, "selected_option_ids": [999999]},
        expected=422,
    )


async def test_audit_rollback_and_future_window(api, monkeypatch):
    from src.modules.audit_security.infrastructure.repository import AuditRepository

    call, engine, cid, _, _, eid, body = await setup_exam(api)
    future = datetime.now(UTC) + timedelta(days=1)
    body.update(opens_at=future.isoformat(), due_at=(future + timedelta(hours=1)).isoformat())
    await call("PUT", f"/courses/{cid}/exams/{eid}", json=body)
    await call("POST", f"/exams/{eid}/publish")
    assert not (await call("GET", f"/exams/{eid}/eligibility", actor="student"))["eligible"]
    await call("POST", f"/exams/{eid}/attempts", actor="student", expected=409)

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(AuditRepository, "append_log", fail_audit)
    # ASGI transport propagates the original exception after the error handler.
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        await call(
            "POST", f"/courses/{cid}/exams", expected=500, json=body | {"title": "MUST_ROLL_BACK"}
        )
    async with engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT COUNT(*) FROM exams WHERE title='MUST_ROLL_BACK'")) == 0
        )
