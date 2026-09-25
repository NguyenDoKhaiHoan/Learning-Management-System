"""Week 3 acceptance tests for private lesson files and learning progress."""

import hashlib

import pytest
from sqlalchemy import text

from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_content, new_course

pytestmark = pytest.mark.integration


async def draft_with_two_lessons(call):
    cid = (await new_course(call))["id"]
    mid, first = await new_content(call, cid)
    second = await call(
        "POST",
        f"/courses/{cid}/modules/{mid}/lessons",
        expected=201,
        json={"title": "Second", "lesson_type": "ARTICLE", "content": "More"},
    )
    return cid, mid, first, second["id"]


async def activate_student(engine, course_id, student_id):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO enrollments (course_id,student_id,status) "
                "VALUES (:course,:student,'ACTIVE')"
            ),
            {"course": course_id, "student": student_id},
        )


async def test_private_file_upload_validation_and_authorized_download(api):
    call, engine, users, tokens, client = api
    cid = (await new_course(call))["id"]
    mid, lid = await new_content(call, cid)
    base = f"/courses/{cid}/modules/{mid}/lessons/{lid}/resources"
    content = b"%PDF-1.7\nprivate lesson file"
    uploaded = await call(
        "POST",
        base + "/file",
        expected=201,
        content=content,
        headers={"Content-Type": "application/pdf", "X-File-Name": "../lesson.pdf"},
    )
    assert uploaded["title"] == "lesson.pdf"
    assert uploaded["size_bytes"] == len(content)
    assert uploaded["sha256"] == hashlib.sha256(content).hexdigest()
    assert "location" not in uploaded
    await call(
        "POST",
        base + "/file",
        expected=422,
        content=b"executable",
        headers={"Content-Type": "application/x-msdownload", "X-File-Name": "bad.exe"},
    )
    await call(
        "POST",
        base + "/file",
        expected=422,
        content=b"not really a PDF",
        headers={"Content-Type": "application/pdf", "X-File-Name": "fake.pdf"},
    )
    await call(
        "POST",
        base + "/file",
        expected=413,
        content=b"x" * 1025,
        headers={"Content-Type": "application/pdf", "X-File-Name": "large.pdf"},
    )
    link = await call(
        "POST",
        base,
        expected=201,
        json={"title": "Reference", "url": "https://example.com/reference"},
    )
    assert link["resource_type"] == "LINK" and "location" not in link
    assert len(await call("GET", base)) == 2
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    download = base + f"/{uploaded['id']}/content"
    await call("GET", download, actor="student", expected=403)
    await activate_student(engine, cid, users["student"])
    response = await client.get(
        "/api/v1" + download,
        headers={"Authorization": "Bearer " + tokens["student"]["access_token"]},
    )
    assert response.status_code == 200 and response.content == content
    assert response.headers["content-type"] == "application/pdf"
    await call("GET", base + f"/{link['id']}/content", actor="student", expected=409)
    await call("DELETE", base + f"/{uploaded['id']}", expected=409)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT location, uploaded_by FROM lesson_resources WHERE id=:id"),
                {"id": uploaded["id"]},
            )
        ).one()
        assert ".." not in row.location and row.uploaded_by == users["owner"]


async def test_progress_state_machine_completion_rule_and_scope(api):
    call, engine, users, _, _ = api
    cid, _, first, second = await draft_with_two_lessons(call)
    rule = await call(
        "PUT", f"/courses/{cid}/completion-rule", json={"required_lesson_percent": 50}
    )
    assert rule["required_lesson_percent"] == 50
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    await activate_student(engine, cid, users["student"])
    path = f"/courses/{cid}/lessons/{first}/progress"
    started = await call(
        "PUT",
        path,
        actor="student",
        json={"status": "IN_PROGRESS", "last_position_seconds": 12},
    )
    assert started["lesson"]["status"] == "IN_PROGRESS"
    assert started["course"]["progress_percent"] == 0
    await call(
        "PUT",
        path,
        actor="student",
        expected=409,
        json={"status": "IN_PROGRESS", "last_position_seconds": 11},
    )
    completed = await call(
        "PUT",
        path,
        actor="student",
        json={"status": "COMPLETED", "last_position_seconds": 12},
    )
    assert completed["course"]["completed_lessons"] == 1
    assert completed["course"]["total_lessons"] == 2
    assert completed["course"]["progress_percent"] == 50
    assert completed["course"]["completed_at"] is not None
    await call(
        "PUT",
        path,
        actor="student",
        expected=409,
        json={"status": "NOT_STARTED", "last_position_seconds": 12},
    )
    summary = await call("GET", f"/courses/{cid}/progress/me", actor="student")
    assert summary["progress_percent"] == 50
    await call("GET", f"/courses/{cid}/progress/me", actor="other", expected=403)
    await call(
        "PUT",
        f"/courses/{cid}/completion-rule",
        expected=409,
        json={"required_lesson_percent": 100},
    )
    await call(
        "PUT",
        f"/courses/{cid}/lessons/{second}/progress",
        actor="student",
        json={"status": "COMPLETED", "last_position_seconds": 0},
    )
    async with engine.connect() as conn:
        actions = set((await conn.execute(text("SELECT action FROM audit_logs"))).scalars())
        assert {
            "completion_rule.update",
            "lesson_progress.in_progress",
            "lesson_progress.completed",
        } <= actions
        assert await conn.scalar(text("SELECT COUNT(*) FROM lesson_progress")) == 2
        assert await conn.scalar(text("SELECT progress_percent FROM course_progress")) == 100


async def test_completion_threshold_uses_exact_ratio_not_rounded_display(api):
    call, engine, users, _, _ = api
    cid, mid, first, second = await draft_with_two_lessons(call)
    third = await call(
        "POST",
        f"/courses/{cid}/modules/{mid}/lessons",
        expected=201,
        json={"title": "Third", "lesson_type": "ARTICLE", "content": "Final"},
    )
    await call("PUT", f"/courses/{cid}/completion-rule", json={"required_lesson_percent": 66.67})
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    await activate_student(engine, cid, users["student"])
    for lesson_id in (first, second):
        result = await call(
            "PUT",
            f"/courses/{cid}/lessons/{lesson_id}/progress",
            actor="student",
            json={"status": "COMPLETED"},
        )
    assert result["course"]["progress_percent"] == 66.67
    assert result["course"]["completed_at"] is None
    result = await call(
        "PUT",
        f"/courses/{cid}/lessons/{third['id']}/progress",
        actor="student",
        json={"status": "COMPLETED"},
    )
    assert result["course"]["completed_at"] is not None
