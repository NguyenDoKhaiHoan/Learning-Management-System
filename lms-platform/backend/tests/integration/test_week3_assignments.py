"""Assignment lifecycle, deadline policy, version history and file scope on MySQL."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.modules.audit_security.infrastructure.repository import AuditRepository
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_content, new_course
from tests.integration.test_week3_learning import activate_student

pytestmark = pytest.mark.integration


def assignment_body(*, late=True, attempts=3):
    now = datetime.now(UTC)
    return {
        "title": "Essay",
        "description": "Submit an answer or PDF",
        "opens_at": (now - timedelta(hours=1)).isoformat(),
        "due_at": (now + timedelta(hours=1)).isoformat(),
        "allow_late": late,
        "late_until": (now + timedelta(hours=2)).isoformat() if late else None,
        "max_attempts": attempts,
        "max_file_bytes": 100,
        "allowed_mime_types": ["application/pdf"],
        "max_score": 100,
    }


async def ready_course(call, engine, users):
    cid = (await new_course(call))["id"]
    await new_content(call, cid)
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    await activate_student(engine, cid, users["student"])
    return cid


async def test_assignment_lifecycle_policy_and_scoped_reads(api):
    call, engine, users, _, _ = api
    cid = await ready_course(call, engine, users)
    base = f"/courses/{cid}/assignments"
    await call("POST", base, actor="student", expected=403, json=assignment_body())
    await call(
        "POST", base, expected=422, json={**assignment_body(), "due_at": "2020-01-01T00:00:00Z"}
    )
    created = await call("POST", base, expected=201, json=assignment_body())
    aid = created["id"]
    assert created["status"] == "DRAFT"
    assert await call("GET", base, actor="student") == []
    await call("GET", base + f"/{aid}", actor="student", expected=404)
    await call(
        "POST",
        base + f"/{aid}/submissions",
        actor="student",
        expected=404,
        json={"answer_text": "early"},
    )
    await call("PUT", base + f"/{aid}", json={**assignment_body(), "title": "Revised"})
    await call("POST", base + f"/{aid}/status", json={"status": "PUBLISHED"})
    assert (await call("GET", base, actor="student"))[0]["title"] == "Revised"
    await call("PUT", base + f"/{aid}", expected=409, json=assignment_body())
    await call("DELETE", base + f"/{aid}", expected=409)
    await call("GET", base, actor="other", expected=403)
    await call("POST", base + f"/{aid}/status", json={"status": "CLOSED"})
    assert len(await call("GET", base, actor="student")) == 1
    await call(
        "POST",
        base + f"/{aid}/submissions",
        actor="student",
        expected=409,
        json={"answer_text": "closed"},
    )
    await call("POST", base + f"/{aid}/status", json={"status": "ARCHIVED"})
    await call("POST", base + f"/{aid}/status", expected=409, json={"status": "PUBLISHED"})
    async with engine.connect() as conn:
        actions = set((await conn.execute(text("SELECT action FROM audit_logs"))).scalars())
        assert {
            "assignment.create",
            "assignment.update",
            "assignment.published",
            "assignment.closed",
            "assignment.archived",
        } <= actions


async def test_versions_late_policy_file_validation_and_private_access(api):
    call, engine, users, tokens, client = api
    cid = await ready_course(call, engine, users)
    base = f"/courses/{cid}/assignments"
    aid = (await call("POST", base, expected=201, json=assignment_body()))["id"]
    await call("POST", base + f"/{aid}/status", json={"status": "PUBLISHED"})
    submissions = base + f"/{aid}/submissions"
    first = await call(
        "POST", submissions, actor="student", expected=201, json={"answer_text": "first answer"}
    )
    assert first["version"] == 1 and first["status"] == "SUBMITTED"
    await call(
        "POST",
        submissions + "/file",
        actor="student",
        expected=422,
        content=b"not a PDF",
        headers={"Content-Type": "application/pdf", "X-File-Name": "fake.pdf"},
    )
    await call(
        "POST",
        submissions + "/file",
        actor="student",
        expected=413,
        content=b"%PDF-" + b"x" * 100,
        headers={"Content-Type": "application/pdf", "X-File-Name": "big.pdf"},
    )
    second = await call(
        "POST",
        submissions + "/file",
        actor="student",
        expected=201,
        content=b"%PDF-1.7\ncontent",
        headers={"Content-Type": "application/pdf", "X-File-Name": "../essay.pdf"},
    )
    assert second["version"] == 2 and second["submitted_by"] == str(users["student"])
    files = await call("GET", submissions + f"/{second['id']}/files", actor="student")
    assert len(files) == 1 and files[0]["title"] == "essay.pdf"
    path = submissions + f"/{second['id']}/files/{files[0]['id']}/content"
    response = await client.get(
        "/api/v1" + path, headers={"Authorization": "Bearer " + tokens["student"]["access_token"]}
    )
    assert response.status_code == 200 and response.content == b"%PDF-1.7\ncontent"
    assert len(await call("GET", submissions, actor="owner")) == 2
    assert [
        row["version"] for row in await call("GET", submissions + "/mine", actor="student")
    ] == [1, 2]
    await call("GET", path, actor="other", expected=403)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE assignments SET due_at=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id=:id"),
            {"id": aid},
        )
    late = await call(
        "POST", submissions, actor="student", expected=201, json={"answer_text": "late answer"}
    )
    assert late["version"] == 3 and late["status"] == "LATE"
    await call("POST", submissions, actor="student", expected=409, json={"answer_text": "fourth"})
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT COUNT(*) FROM assignment_submissions")) == 3
        assert await conn.scalar(text("SELECT COUNT(*) FROM submission_files")) == 1
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE enrollments SET status='SUSPENDED' WHERE course_id=:id"), {"id": cid}
        )
    await call(
        "POST", submissions, actor="student", expected=403, json={"answer_text": "suspended"}
    )
    await call("GET", path, actor="student", expected=403)


async def test_deadline_rejection_and_audit_failure_roll_back_submission(api, monkeypatch):
    call, engine, users, _, _ = api
    cid = await ready_course(call, engine, users)
    base = f"/courses/{cid}/assignments"
    aid = (await call("POST", base, expected=201, json=assignment_body(late=False)))["id"]
    await call("POST", base + f"/{aid}/status", json={"status": "PUBLISHED"})
    submissions = base + f"/{aid}/submissions"

    async def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    with monkeypatch.context() as patcher:
        patcher.setattr(AuditRepository, "append_log", fail)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await call(
                "POST",
                submissions,
                actor="student",
                expected=201,
                json={"answer_text": "must roll back"},
            )
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT COUNT(*) FROM assignment_submissions")) == 0
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE assignments SET due_at=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id=:id"),
            {"id": aid},
        )
    await call("POST", submissions, actor="student", expected=409, json={"answer_text": "too late"})


async def test_concurrent_attempts_cannot_exceed_limit(api):
    call, engine, users, tokens, client = api
    cid = await ready_course(call, engine, users)
    base = f"/courses/{cid}/assignments"
    aid = (await call("POST", base, expected=201, json=assignment_body(attempts=1)))["id"]
    await call("POST", base + f"/{aid}/status", json={"status": "PUBLISHED"})
    url = f"/api/v1{base}/{aid}/submissions"
    headers = {"Authorization": "Bearer " + tokens["student"]["access_token"]}
    responses = await asyncio.gather(
        *[client.post(url, headers=headers, json={"answer_text": "attempt"}) for _ in range(2)]
    )
    assert sorted(response.status_code for response in responses) == [201, 409]


async def test_completion_rule_requires_published_assignment_submission(api):
    call, engine, users, _, _ = api
    cid = (await new_course(call))["id"]
    _, lesson_id = await new_content(call, cid)
    await call(
        "PUT",
        f"/courses/{cid}/completion-rule",
        json={"required_lesson_percent": 100, "require_submitted_assignments": True},
    )
    base = f"/courses/{cid}/assignments"
    assignment_id = (await call("POST", base, expected=201, json=assignment_body()))["id"]
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    await call("POST", base + f"/{assignment_id}/status", json={"status": "PUBLISHED"})
    await activate_student(engine, cid, users["student"])
    lesson = await call(
        "PUT",
        f"/courses/{cid}/lessons/{lesson_id}/progress",
        actor="student",
        json={"status": "COMPLETED"},
    )
    assert lesson["course"]["completed_assignments"] == 0
    assert lesson["course"]["total_assignments"] == 1
    assert lesson["course"]["progress_percent"] == 50
    assert lesson["course"]["completed_at"] is None
    await call(
        "POST",
        base + f"/{assignment_id}/submissions",
        actor="student",
        expected=201,
        json={"answer_text": "submitted"},
    )
    progress = await call("GET", f"/courses/{cid}/progress/me", actor="student")
    assert progress["completed_assignments"] == 1
    assert progress["progress_percent"] == 100
    assert progress["completed_at"] is not None
