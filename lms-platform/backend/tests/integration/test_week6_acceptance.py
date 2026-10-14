"""MVP acceptance across modules, using public HTTP APIs and disposable MySQL."""

import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.jobs.processors.exports import process_exports
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week3_assignments import assignment_body
from tests.integration.test_week4_exams import setup_exam

pytestmark = [pytest.mark.integration, pytest.mark.acceptance]


async def test_mvp_enrollment_learning_assessments_completion_reports_and_audit(api):
    call, engine, cid, _, question, eid, _ = await setup_exam(api, enroll=False)
    _, _, users, tokens, client = api
    await call("POST", f"/courses/{cid}/status", json={"status": "DRAFT"})
    await call(
        "PUT",
        f"/courses/{cid}/completion-rule",
        json={
            "required_lesson_percent": 100,
            "require_submitted_assignments": True,
            "require_published_assignment_grades": True,
            "require_published_exam_grades": True,
            "minimum_grade_percent": 80,
        },
    )
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    enrollment_path = f"/courses/{cid}/enrollments"
    enrollment = await call("POST", enrollment_path, actor="student", expected=201, json={})
    assert enrollment["status"] == "PENDING"
    await call("POST", enrollment_path, actor="student", expected=409, json={})
    await call("GET", f"/courses/{cid}/modules", actor="student", expected=403)
    await call("PATCH", f"{enrollment_path}/{users['student']}", json={"status": "ACTIVE"})
    assignments = f"/courses/{cid}/assignments"
    assignment = await call("POST", assignments, expected=201, json=assignment_body(attempts=2))
    base = f"{assignments}/{assignment['id']}"
    await call("POST", base + "/status", json={"status": "PUBLISHED"})
    await call("POST", f"/exams/{eid}/publish")
    modules = await call("GET", f"/courses/{cid}/modules", actor="student")
    lesson = modules[0]["lessons"][0]["id"]
    progress_path = f"/courses/{cid}/progress/me"
    for status in ("IN_PROGRESS", "COMPLETED"):
        await call(
            "PUT",
            f"/courses/{cid}/lessons/{lesson}/progress",
            actor="student",
            json={"status": status},
        )
    progress = await call("GET", progress_path, actor="student")
    assert progress["completed_lessons"] == 1 and progress["completed_at"] is None

    first = await call(
        "POST",
        base + "/submissions",
        actor="student",
        expected=201,
        json={"answer_text": "Bản đầu tiên"},
    )
    final = await call(
        "POST",
        base + "/submissions",
        actor="student",
        expected=201,
        json={"answer_text": "Bài hoàn chỉnh 🎓"},
    )
    assert final["version"] == 2 and final["submitted_by"] == str(users["student"])
    assert final["submitted_at"] >= first["submitted_at"]
    await call(
        "POST",
        base + "/submissions",
        actor="student",
        expected=409,
        json={"answer_text": "Over the limit"},
    )
    history = await call("GET", base + "/submissions/mine", actor="student")
    assert [s["answer_text"] for s in history] == ["Bản đầu tiên", "Bài hoàn chỉnh 🎓"]
    grade = await call(
        "POST",
        f"/courses/{cid}/grades",
        expected=201,
        json={
            "enrollment_id": enrollment["id"],
            "assessment_type": "ASSIGNMENT",
            "assessment_id": assignment["id"],
            "source_id": final["id"],
            "feedback": "Đạt yêu cầu",
            "items": [{"item_key": "essay", "label": "Essay", "score": 85, "max_score": 100}],
        },
    )
    assert await call("GET", f"/courses/{cid}/grades/me", actor="student") == []
    attempt = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    answer = {"selected_option_ids": [question["options"][0]["id"]], "expected_version": 0}
    await call(
        "PUT",
        f"/attempts/{attempt['id']}/answers/{question['id']}",
        actor="student",
        json=answer,
    )
    resumed = await call("GET", f"/attempts/{attempt['id']}", actor="student")
    assert resumed["expires_at"] == attempt["expires_at"]
    assert resumed["answers"][0]["selected_option_ids"] == answer["selected_option_ids"]
    submitted = await call("POST", f"/attempts/{attempt['id']}/submit", actor="student")
    repeated = await call("POST", f"/attempts/{attempt['id']}/submit", actor="student")
    assert (
        submitted["status"] == "SUBMITTED"
        and repeated["server_version"] == submitted["server_version"]
    )
    grades = await call("GET", f"/courses/{cid}/grades")
    assert len(grades) == 2 and all(g["status"] == "DRAFT" for g in grades)
    for item in grades:
        await call("POST", f"/grades/{item['id']}/publish", json={"expected_version": 1})
    visible = await call("GET", f"/courses/{cid}/grades/me", actor="student")
    assert len(visible) == 2 and all(g["status"] == "PUBLISHED" for g in visible)
    assert next(g for g in visible if g["id"] == grade["id"])["feedback"] == "Đạt yêu cầu"
    progress = await call("GET", progress_path, actor="student")
    assert Decimal(str(progress["progress_percent"])) == 100
    assert (
        progress["completed_at"] and progress["passed_assignments"] == progress["passed_exams"] == 1
    )
    assert (await call("GET", "/enrollments/me", actor="student"))[0]["status"] == "ACTIVE"

    thread = await call(
        "POST",
        f"/courses/{cid}/forum/threads",
        actor="student",
        expected=201,
        json={"title": "Thảo luận kết quả", "body": "Em đã hoàn thành."},
    )
    discussion = f"/courses/{cid}/forum/threads/{thread['id']}"
    await call("POST", discussion + "/messages", expected=201, json={"body": "Đã nhận bài."})
    assert (await call("GET", discussion, actor="student"))["messages"][0]["body"] == "Đã nhận bài."
    notices = await call("GET", "/notifications", actor="student")
    assert sum(n["type"] == "GRADE_PUBLISHED" for n in notices["items"]) == 2
    await call("POST", "/notifications/read-all", actor="student")
    assert (await call("GET", "/notifications/unread-count", actor="student"))["unread"] == 0

    report = await call("GET", f"/reports/courses/{cid}/learners", actor="owner")
    assert report["total"] == report["totals"]["completed_learners"] == 1
    job = await call(
        "POST",
        "/exports",
        expected=202,
        json={"request_id": str(uuid4()), "kind": "GRADEBOOK", "course_id": cid, "filters": {}},
    )
    assert await process_exports(engine, client._transport.app.state.settings) == 1
    response = await client.get(
        f"/api/v1/exports/{job['id']}/content",
        headers={"Authorization": "Bearer " + tokens["owner"]["access_token"]},
    )
    assert response.status_code == 200
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 2 and {row["status"] for row in rows} == {"PUBLISHED"}
    assert {row["assessment_type"] for row in rows} == {"ASSIGNMENT", "EXAM"}
    logs = await call("GET", "/audit/logs?limit=100", actor="admin")
    assert {
        "course.published",
        "enrollment.request",
        "enrollment.active",
        "assignment.submit",
        "attempt.submit",
        "grade.publish",
        "export.request",
        "export.ready",
        "export.download",
    } <= {log["action"] for log in logs["items"]}


@pytest.mark.parametrize(
    "allow_late,late_hours,expected",
    [(False, None, 409), (True, 1, 201), (True, -0.5, 409)],
    ids=["late-disabled", "inside-late-window", "late-window-closed"],
)
async def test_assignment_deadline_acceptance_preserves_history(
    api, allow_late, late_hours, expected
):
    call, engine, cid, _, _, _, _ = await setup_exam(api)
    base = f"/courses/{cid}/assignments"
    assignment = await call(
        "POST",
        base,
        expected=201,
        json=assignment_body(late=allow_late),
    )
    path = f"{base}/{assignment['id']}"
    await call("POST", path + "/status", json={"status": "PUBLISHED"})
    original = await call(
        "POST",
        path + "/submissions",
        actor="student",
        expected=201,
        json={"answer_text": "On time"},
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE assignments SET opens_at=:opens,due_at=:due,late_until=:late WHERE id=:id"
            ),
            {
                "opens": now - timedelta(hours=2),
                "due": now - timedelta(hours=1),
                "late": now + timedelta(hours=late_hours) if late_hours is not None else None,
                "id": assignment["id"],
            },
        )
    late = await call(
        "POST",
        path + "/submissions",
        actor="student",
        expected=expected,
        json={"answer_text": "After deadline"},
    )
    history = await call("GET", path + "/submissions/mine", actor="student")
    assert history[0] == original and original["status"] == "SUBMITTED"
    if expected == 201:
        assert late["status"] == "LATE" and late["version"] == 2 and len(history) == 2
    else:
        assert len(history) == 1
    async with engine.connect() as conn:
        assert await conn.scalar(
            text("SELECT COUNT(*) FROM audit_logs WHERE action='assignment.submit'")
        ) == len(history)
