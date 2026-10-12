"""Audited MVP writes and immutable Admin projections on real MySQL."""

import pytest
from sqlalchemy import text

from src.modules.audit_security.infrastructure.repository import AuditRepository
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_content, new_course
from tests.integration.test_week3_assignments import assignment_body
from tests.integration.test_week4_grading import content, submitted

pytestmark = pytest.mark.integration


async def test_audit_publish_permissions_grade_submission_and_filtering(api):
    call, engine, cid, _, _, _, grade = await submitted(api)
    _, _, users, _, _ = api
    grade = await call("PUT", f"/grades/{grade['id']}", json=content(grade["version"]))
    grade = await call(
        "POST", f"/grades/{grade['id']}/publish", json={"expected_version": grade["version"]}
    )
    await call(
        "POST",
        f"/grades/{grade['id']}/revise",
        json=content(grade["version"], 9) | {"reason": "Rubric correction"},
    )
    await call("PUT", f"/users/{users['student']}/roles/INSTRUCTOR", actor="admin", expected=201)
    await call("DELETE", f"/users/{users['student']}/roles/INSTRUCTOR", actor="admin")
    await call("DELETE", "/roles/INSTRUCTOR/permissions/course.publish", actor="admin")
    await call("PUT", "/roles/INSTRUCTOR/permissions/course.publish", actor="admin")
    base = f"/courses/{cid}/assignments"
    assignment = await call("POST", base, json=assignment_body(), expected=201)
    await call("POST", f"{base}/{assignment['id']}/status", json={"status": "PUBLISHED"})
    submission = await call(
        "POST",
        f"{base}/{assignment['id']}/submissions",
        actor="student",
        expected=201,
        json={"answer_text": "Private answer"},
        headers={"X-Trace-ID": "audit-submission-proof"},
    )
    page = await call("GET", "/audit/logs?limit=100", actor="admin")
    assert {
        "course.published",
        "exam.publish",
        "grade.publish",
        "grade.revise",
        "role.assign",
        "role.revoke",
        "permission.grant",
        "permission.revoke",
        "assignment.published",
        "assignment.submit",
        "attempt.submit",
    } <= {r["action"] for r in page["items"]}
    filtered = await call("GET", "/audit/logs?trace_id=audit-submission-proof", actor="admin")
    row = next(r for r in filtered["items"] if r["action"] == "assignment.submit")
    assert row["resource_id"] == submission["id"] and row["actor_id"] == str(users["student"])
    assert row["details"]["course_id"] == cid and row["details"]["submission_type"] == "TEXT"
    assert "Private answer" not in str(page) and "password" not in str(page)
    first = await call("GET", "/audit/logs?limit=1", actor="admin")
    second = await call("GET", "/audit/logs?limit=1&offset=1", actor="admin")
    assert first["total"] == second["total"] and first["items"][0]["id"] != second["items"][0]["id"]
    for actor in ("student", "owner", None):
        await call("GET", "/audit/logs", actor=actor, expected=401 if actor is None else 403)
    await call("GET", "/audit/logs?limit=101", actor="admin", expected=422)
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT COUNT(*) FROM audit_logs")) == page["total"]


@pytest.mark.parametrize("action", ["course.published", "role.assign", "permission.revoke"])
async def test_audit_failure_rolls_back_sensitive_mutations(api, monkeypatch, action):
    call, engine, users, _, _ = api
    cid = (await new_course(call))["id"]
    await new_content(call, cid)
    original = AuditRepository.append_log

    async def fail(self, **kwargs):
        if kwargs["action"] == action:
            raise RuntimeError("audit unavailable")
        return await original(self, **kwargs)

    monkeypatch.setattr(AuditRepository, "append_log", fail)
    with pytest.raises(RuntimeError):
        if action == "course.published":
            await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
        elif action == "role.assign":
            await call("PUT", f"/users/{users['student']}/roles/INSTRUCTOR", actor="admin")
        else:
            await call("DELETE", "/roles/INSTRUCTOR/permissions/course.publish", actor="admin")
    async with engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT status FROM courses WHERE id=:id"), {"id": cid})
            == "DRAFT"
        )
        assert await conn.scalar(text("SELECT COUNT(*) FROM user_roles")) == 4
        assert await conn.scalar(text("SELECT COUNT(*) FROM role_permissions")) == 7
        assert (
            await conn.scalar(
                text("SELECT COUNT(*) FROM audit_logs WHERE action=:action"), {"action": action}
            )
            == 0
        )
