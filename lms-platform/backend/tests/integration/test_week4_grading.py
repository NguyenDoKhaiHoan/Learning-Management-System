"""Real MySQL submit, deadline, grade publication and revision acceptance."""

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import text

from src.jobs.processors.exam_expiry import sweep_expired
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.gradebook.application.service import GradeService
from src.modules.quiz_exam.application.service import ExamService
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week3_assignments import assignment_body, ready_course
from tests.integration.test_week4_exams import setup_exam

pytestmark = pytest.mark.integration


async def submitted(api, *, correct=True):
    call, engine, cid, _, q, eid, _ = await setup_exam(api)
    await call("POST", f"/exams/{eid}/publish")
    attempt = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    if correct:
        await call(
            "PUT",
            f"/attempts/{attempt['id']}/answers/{q['id']}",
            actor="student",
            json={"selected_option_ids": [q["options"][0]["id"]], "expected_version": 0},
        )
    await call("POST", f"/attempts/{attempt['id']}/submit", actor="student")
    grade = (await call("GET", f"/courses/{cid}/grades"))[0]
    return call, engine, cid, q, eid, attempt, grade


def content(version, score=8):
    return {
        "expected_version": version,
        "feedback": "Đã xem bài 🎓",
        "items": [
            {
                "item_key": "overall",
                "label": "Result",
                "score": score,
                "max_score": 10,
                "feedback": "Giải thích rõ hơn",
            }
        ],
    }


async def test_grade_draft_publish_revise_history_and_visibility(api):
    call, engine, cid, _, _, attempt, grade = await submitted(api)
    gid = grade["id"]
    assert Decimal(grade["score"]) == 10 and grade["status"] == "DRAFT"
    assert grade["source_attempt_id"] == int(attempt["id"])
    assert await call("GET", f"/courses/{cid}/grades/me", actor="student") == []
    await call("GET", f"/grades/{gid}", actor="student", expected=403)
    await call("GET", f"/grades/{gid}/history", actor="student", expected=403)
    await call("GET", f"/grades/{gid}", actor="other", expected=403)
    await call(
        "POST",
        f"/grades/{gid}/publish",
        actor="student",
        expected=403,
        json={"expected_version": 1},
    )
    draft = await call("PUT", f"/grades/{gid}", json=content(grade["version"]))
    assert draft["version"] == 2 and Decimal(draft["score"]) == 8
    await call("PUT", f"/grades/{gid}", json=content(1), expected=409)
    published = await call("POST", f"/grades/{gid}/publish", json={"expected_version": 2})
    student = (await call("GET", f"/courses/{cid}/grades/me", actor="student"))[0]
    assert student["feedback"] == "Đã xem bài 🎓" and Decimal(student["score"]) == 8
    assert student["items"][0]["feedback"] == "Giải thích rõ hơn"
    await call("PUT", f"/grades/{gid}", json=content(3), expected=409)
    await call("POST", f"/grades/{gid}/revise", json=content(3), expected=422)
    revised = await call(
        "POST", f"/grades/{gid}/revise", json=content(3, 9) | {"reason": "Correct rubric"}
    )
    assert revised["status"] == "DRAFT" and revised["published_at"] is None
    assert await call("GET", f"/courses/{cid}/grades/me", actor="student") == []
    final = await call("POST", f"/grades/{gid}/publish", json={"expected_version": 4})
    repeated = await call("POST", f"/grades/{gid}/publish", json={"expected_version": 4})
    assert repeated["version"] == final["version"] == 5
    history = await call("GET", f"/grades/{gid}/history")
    assert [h["action"] for h in history] == ["AUTO_GRADE", "DRAFT", "PUBLISH", "REVISE", "PUBLISH"]
    assert Decimal(history[2]["snapshot"]["score"]) == 8
    assert history[3]["reason"] == "Correct rubric"
    assert published["published_at"] is not None
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT COUNT(*) FROM grade_history")) == 5
        assert (
            await conn.scalar(text("SELECT COUNT(*) FROM audit_logs WHERE action LIKE 'grade.%'"))
            == 5
        )


@pytest.mark.parametrize("question_type", ["SINGLE", "MULTIPLE", "TRUE_FALSE"])
async def test_exact_set_snapshot_grading_and_decimal_points(api, question_type):
    call, engine, cid, bid, q, eid, body = await setup_exam(api)
    options = [
        {"key": "A", "text": "Correct", "is_correct": True},
        {"key": "B", "text": "Also correct", "is_correct": question_type == "MULTIPLE"},
    ]
    if question_type != "TRUE_FALSE":
        options.append({"key": "C", "text": "Wrong"})
    q2 = await call(
        "POST",
        f"/question-banks/{bid}/questions",
        expected=201,
        json={"question_type": question_type, "prompt": "Key snapshot", "options": options},
    )
    body["questions"] = [
        {"question_id": q["id"], "position": 1, "points": 0.1},
        {"question_id": q2["id"], "position": 2, "points": 0.2},
    ]
    await call("PUT", f"/courses/{cid}/exams/{eid}", json=body)
    await call("POST", f"/exams/{eid}/publish")
    for attempt_no in range(2):
        a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
        # Partial multiple selections must get zero; no partial credit.
        selected = [o["id"] for o in q2["options"] if o["is_correct"]]
        if attempt_no == 0:
            selected = selected[:1] if question_type == "MULTIPLE" else []
        else:
            await call(
                "PUT",
                f"/attempts/{a['id']}/answers/{q['id']}",
                actor="student",
                json={"selected_option_ids": [q["options"][0]["id"]], "expected_version": 0},
            )
            # Mutate the bank key after start; grading must use the immutable attempt key.
            async with engine.begin() as conn:
                await conn.execute(
                    text("UPDATE question_options SET is_correct=0 WHERE question_id=:q"),
                    {"q": q2["id"]},
                )
        await call(
            "PUT",
            f"/attempts/{a['id']}/answers/{q2['id']}",
            actor="student",
            json={"selected_option_ids": selected, "expected_version": attempt_no},
        )
        response = await call("POST", f"/attempts/{a['id']}/submit", actor="student")
        assert "score" not in response and "is_correct" not in str(response)
        async with engine.connect() as conn:
            score = await conn.scalar(
                text("SELECT score FROM exam_attempts WHERE id=:id"), {"id": a["id"]}
            )
            assert score == (Decimal("0") if attempt_no == 0 else Decimal("0.3"))
    grades = await call("GET", f"/courses/{cid}/grades")
    assert len(grades) == 1 and Decimal(grades[0]["score"]) == Decimal("0.3")
    assert grades[0]["source_attempt_id"] == int(a["id"])
    assert len(await call("GET", f"/grades/{grades[0]['id']}/history")) == 2


async def expire_in_sql(engine, aid):
    async with engine.begin() as conn:
        await conn.execute(
            text("""UPDATE exam_attempts
            SET started_at=UTC_TIMESTAMP(6)-INTERVAL 10 MINUTE,
            expires_at=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id=:id"""),
            {"id": aid},
        )


async def test_worker_and_submit_race_are_idempotent_and_reject_late_save(api):
    call, engine, cid, _, q, eid, _ = await setup_exam(api)
    await call("POST", f"/exams/{eid}/publish")
    a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    await call(
        "PUT",
        f"/attempts/{a['id']}/answers/{q['id']}",
        actor="student",
        json={"selected_option_ids": [q["options"][0]["id"]], "expected_version": 0},
    )
    await expire_in_sql(engine, a["id"])
    await asyncio.gather(
        sweep_expired(engine),
        sweep_expired(engine),
        *[call("POST", f"/attempts/{a['id']}/submit", actor="student") for _ in range(2)],
    )
    assert await sweep_expired(engine) == 0
    await call(
        "PUT",
        f"/attempts/{a['id']}/answers/{q['id']}",
        actor="student",
        expected=409,
        json={"selected_option_ids": [], "expected_version": 2},
    )
    async with engine.connect() as conn:
        attempt = (
            (await conn.execute(text("SELECT * FROM exam_attempts WHERE id=:id"), {"id": a["id"]}))
            .mappings()
            .one()
        )
        assert attempt["status"] == "AUTO_SUBMITTED" and attempt["score"] == 10
        assert attempt["submitted_at"] == attempt["expires_at"] and attempt["server_version"] == 2
        assert await conn.scalar(text("SELECT COUNT(*) FROM grade_history")) == 1
        assert (
            await conn.scalar(text("SELECT COUNT(*) FROM audit_logs WHERE action='attempt.expire'"))
            == 1
        )
    grade = (await call("GET", f"/courses/{cid}/grades"))[0]
    assert Decimal(grade["score"]) == 10


async def test_worker_grades_without_requests_even_after_enrollment_revoked(api):
    call, engine, cid, _, _, eid, _ = await setup_exam(api)
    await call("POST", f"/exams/{eid}/publish")
    a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    await expire_in_sql(engine, a["id"])
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE enrollments SET status='SUSPENDED' WHERE course_id=:cid"), {"cid": cid}
        )
    assert await sweep_expired(engine) == 1
    assert Decimal((await call("GET", f"/courses/{cid}/grades"))[0]["score"]) == 0
    await call("GET", f"/courses/{cid}/grades/me", actor="student", expected=403)


async def test_manual_or_published_grades_survive_later_attempts(api):
    call, engine, cid, q, eid, _, grade = await submitted(api, correct=False)
    grade = await call("PUT", f"/grades/{grade['id']}", json=content(grade["version"], 7))
    grade = await call(
        "POST", f"/grades/{grade['id']}/publish", json={"expected_version": grade["version"]}
    )
    a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    await call(
        "PUT",
        f"/attempts/{a['id']}/answers/{q['id']}",
        actor="student",
        json={"selected_option_ids": [q["options"][0]["id"]], "expected_version": 0},
    )
    await call("POST", f"/attempts/{a['id']}/submit", actor="student")
    final = (await call("GET", f"/courses/{cid}/grades"))[0]
    assert final["version"] == grade["version"] and Decimal(final["score"]) == 7
    async with engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT score FROM exam_attempts WHERE id=:id"), {"id": a["id"]})
            == 10
        )


async def test_submit_and_worker_rollback_on_audit_failure(api, monkeypatch):
    call, engine, cid, _, _, eid, _ = await setup_exam(api)
    await call("POST", f"/exams/{eid}/publish")
    a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    original = AuditRepository.append_log

    async def fail_grade_audit(self, **kwargs):
        if kwargs["action"] == "grade.auto_grade":
            raise RuntimeError("Audit unavailable")
        return await original(self, **kwargs)

    monkeypatch.setattr(AuditRepository, "append_log", fail_grade_audit)
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        await call("POST", f"/attempts/{a['id']}/submit", actor="student", expected=500)
    async with engine.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT status FROM exam_attempts WHERE id=:id"), {"id": a["id"]}
            )
            == "IN_PROGRESS"
        )
        assert await conn.scalar(text("SELECT COUNT(*) FROM gradebook_entries")) == 0
        assert await conn.scalar(text("SELECT COUNT(*) FROM grade_history")) == 0
        assert (
            await conn.scalar(
                text("SELECT COUNT(*) FROM exam_answers WHERE points_awarded IS NOT NULL")
            )
            == 0
        )
    await expire_in_sql(engine, a["id"])
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        await sweep_expired(engine)
    monkeypatch.setattr(AuditRepository, "append_log", original)
    assert await sweep_expired(engine) == 1
    assert len(await call("GET", f"/courses/{cid}/grades")) == 1


async def test_publish_rollback_and_concurrent_grade_edits(api, monkeypatch):
    call, engine, _, _, _, _, grade = await submitted(api)
    gid = grade["id"]
    original = AuditRepository.append_log

    async def fail(self, **kwargs):
        if kwargs["action"] == "grade.publish":
            raise RuntimeError("Audit unavailable")
        return await original(self, **kwargs)

    monkeypatch.setattr(AuditRepository, "append_log", fail)
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        await call("POST", f"/grades/{gid}/publish", json={"expected_version": 1}, expected=500)
    assert (await call("GET", f"/grades/{gid}"))["status"] == "DRAFT"
    assert len(await call("GET", f"/grades/{gid}/history")) == 1
    monkeypatch.setattr(AuditRepository, "append_log", original)
    _, _, _, tokens, client = api
    responses = await asyncio.gather(
        *[
            client.put(
                f"/api/v1/grades/{gid}",
                json=content(1, n),
                headers={"Authorization": "Bearer " + tokens["owner"]["access_token"]},
            )
            for n in (7, 8)
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert len(await call("GET", f"/grades/{gid}/history")) == 2


async def test_manual_assignment_items_validation_source_scope_and_ownership(api):
    call, engine, users, _, _ = api
    cid = await ready_course(call, engine, users)
    base = f"/courses/{cid}/assignments"
    a = await call("POST", base, expected=201, json=assignment_body())
    await call("POST", f"{base}/{a['id']}/status", json={"status": "PUBLISHED"})
    submission = await call(
        "POST",
        f"{base}/{a['id']}/submissions",
        actor="student",
        expected=201,
        json={"answer_text": "My answer"},
    )
    async with engine.begin() as conn:
        enrollment = await conn.scalar(
            text("SELECT id FROM enrollments WHERE course_id=:cid"), {"cid": cid}
        )
        await conn.execute(
            text(
                "INSERT INTO user_roles(user_id,role_id) "
                "SELECT :uid,id FROM roles WHERE code='STUDENT'"
            ),
            {"uid": users["other"]},
        )
        await conn.execute(
            text(
                "INSERT INTO enrollments(course_id,student_id,status) VALUES (:cid,:uid,'ACTIVE')"
            ),
            {"cid": cid, "uid": users["other"]},
        )
    body = {
        "enrollment_id": enrollment,
        "assessment_type": "ASSIGNMENT",
        "assessment_id": a["id"],
        "source_id": submission["id"],
        "feedback": "Reviewed",
        "items": [{"item_key": "rubric", "label": "Rubric", "score": 90, "max_score": 100}],
    }
    await call("POST", f"/courses/{cid}/grades", json=body | {"source_id": 999999}, expected=422)
    await call(
        "POST", f"/courses/{cid}/grades", json=body | {"enrollment_id": 999999}, expected=422
    )
    for items in (
        [body["items"][0]] * 2,
        [body["items"][0] | {"score": 101}],
        [body["items"][0] | {"max_score": 99}],
        [body["items"][0] | {"score": "NaN"}],
    ):
        await call("POST", f"/courses/{cid}/grades", json=body | {"items": items}, expected=422)
    grade = await call("POST", f"/courses/{cid}/grades", json=body, expected=201)
    await call("POST", f"/courses/{cid}/grades", json=body, expected=409)
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    assert len(await call("GET", f"/courses/{cid}/grades/me", actor="student")) == 1
    assert await call("GET", f"/courses/{cid}/grades/me", actor="other") == []


async def test_submit_reads_answer_committed_while_waiting_for_course_lock(api, monkeypatch):
    call, engine, cid, _, q, eid, _ = await setup_exam(api)
    await call("POST", f"/exams/{eid}/publish")
    a = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    authenticated = asyncio.Event()
    original = ExamService.exam

    async def signal(self, *args, **kwargs):
        authenticated.set()
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(ExamService, "exam", signal)
    async with engine.begin() as conn:
        await conn.execute(text("SELECT id FROM courses WHERE id=:id FOR UPDATE"), {"id": cid})
        request = asyncio.create_task(call("POST", f"/attempts/{a['id']}/submit", actor="student"))
        await asyncio.wait_for(authenticated.wait(), timeout=10)
        # Authentication established a REPEATABLE READ snapshot before this commit.
        await conn.execute(
            text("""INSERT INTO exam_answers(attempt_id,question_id,selected_option_ids,answered_at)
                VALUES (:a,:q,:options,UTC_TIMESTAMP(6))"""),
            {"a": a["id"], "q": q["id"], "options": "[" + str(q["options"][0]["id"]) + "]"},
        )
        await conn.execute(
            text("UPDATE exam_attempts SET server_version=1 WHERE id=:id"), {"id": a["id"]}
        )
    await asyncio.wait_for(request, timeout=10)
    assert Decimal((await call("GET", f"/courses/{cid}/grades"))[0]["score"]) == 10


async def test_student_read_does_not_leak_grade_revised_while_waiting_for_lock(api, monkeypatch):
    call, engine, cid, _, _, _, grade = await submitted(api)
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    authenticated = asyncio.Event()
    original = GradeService.list

    async def signal(self, *args, **kwargs):
        authenticated.set()
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(GradeService, "list", signal)
    async with engine.begin() as conn:
        await conn.execute(text("SELECT id FROM courses WHERE id=:id FOR UPDATE"), {"id": cid})
        request = asyncio.create_task(call("GET", f"/courses/{cid}/grades/me", actor="student"))
        await asyncio.wait_for(authenticated.wait(), timeout=10)
        await conn.execute(
            text("""UPDATE gradebook_entries SET status='DRAFT',published_at=NULL,
                score=9,version=version+1 WHERE id=:id"""),
            {"id": grade["id"]},
        )
    assert await asyncio.wait_for(request, timeout=10) == []
