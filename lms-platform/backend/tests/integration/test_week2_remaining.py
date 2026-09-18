"""Enrollment/staff authorization, full week-two journey and repeatable demo data."""

import asyncio

import pytest
from sqlalchemy import text

from scripts.seed_week2 import DEMO_PASSWORD, seed_demo
from src.modules.audit_security.infrastructure.repository import AuditRepository
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_content, new_course

pytestmark = pytest.mark.integration


async def published_course(call):
    cid = (await new_course(call))["id"]
    mid, lid = await new_content(call, cid)
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    return cid, f"/courses/{cid}/modules/{mid}/lessons/{lid}"


async def test_auth_publish_enrollment_active_suspended_journey(api):
    call, engine, users, _, _ = api
    cid, lesson = await published_course(call)
    base = f"/courses/{cid}/enrollments"
    student = users["student"]
    catalog = await call("GET", "/catalog/courses", actor="student")
    assert catalog[0]["id"] == cid
    assert "content" not in catalog[0]
    await call("GET", lesson, actor="student", expected=403)
    row = await call("POST", base, actor="student", expected=201, json={})
    assert row["status"] == "PENDING" and row["student_id"] == str(student)
    assert (await call("GET", "/enrollments/me", actor="student"))[0]["status"] == "PENDING"
    await call("GET", lesson, actor="student", expected=403)
    await call(
        "PATCH", base + f"/{student}", actor="student", expected=403, json={"status": "ACTIVE"}
    )
    await call("PATCH", base + f"/{student}", json={"status": "ACTIVE"})
    assert (await call("GET", lesson, actor="student"))["content"] == "Text"
    assert (await call("GET", base))[0]["status"] == "ACTIVE"
    await call("PATCH", base + f"/{student}", json={"status": "SUSPENDED"})
    await call("GET", lesson, actor="student", expected=403)
    await call("PATCH", base + f"/{student}", json={"status": "ACTIVE"})
    assert (await call("GET", lesson, actor="student"))["content"] == "Text"
    async with engine.connect() as conn:
        actions = set((await conn.execute(text("SELECT action FROM audit_logs"))).scalars())
        assert {
            "course.published",
            "enrollment.request",
            "enrollment.active",
            "enrollment.suspended",
        } <= actions


async def test_enrollment_scope_validation_and_current_account_state(api):
    call, engine, users, _, _ = api
    cid = (await new_course(call))["id"]
    base = f"/courses/{cid}/enrollments"
    await call("POST", base, actor="student", expected=409, json={})
    assert await call("GET", "/catalog/courses", actor="student") == []
    await new_content(call, cid)
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    await call("POST", base, actor=None, expected=401, json={})
    await call("POST", base, actor="student", expected=403, json={"student_id": users["other"]})
    await call("POST", base, actor="student", expected=422, json={"status": "ACTIVE"})
    await call("POST", base, actor="other", expected=403, json={"student_id": users["student"]})
    await call("GET", base, actor="other", expected=403)
    await call("GET", base, actor="student", expected=403)
    await call("POST", base, expected=404, json={"student_id": 999999})
    await call("POST", base, expected=409, json={"student_id": users["other"]})
    await call("POST", base, actor="admin", expected=201, json={"student_id": users["student"]})
    await call("POST", base, actor="student", expected=409, json={})
    sid = users["student"]
    await call("PATCH", base + f"/{sid}", expected=409, json={"status": "SUSPENDED"})
    await call("PATCH", base + "/999999", expected=404, json={"status": "ACTIVE"})
    await call("PATCH", base + f"/{sid}", expected=422, json={"status": "COMPLETED"})
    await call("PATCH", f"/auth/users/{sid}/status", actor="admin", json={"status": "LOCKED"})
    await call("PATCH", base + f"/{sid}", expected=409, json={"status": "ACTIVE"})
    await call("PATCH", f"/auth/users/{sid}/status", actor="admin", json={"status": "ACTIVE"})
    await call("POST", f"/courses/{cid}/status", json={"status": "DRAFT"})
    await call("PATCH", base + f"/{sid}", expected=409, json={"status": "ACTIVE"})
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE courses SET deleted_at=UTC_TIMESTAMP(6) WHERE id=:id"), {"id": cid}
        )
    await call("POST", base, actor="student", expected=404, json={})
    assert await call("GET", "/enrollments/me", actor="student") == []


async def test_staff_admin_assignment_revocation_and_assistant_scope(api):
    call, _, users, _, _ = api
    cid, _ = await published_course(call)
    base = f"/courses/{cid}/staff"
    target = users["other"]
    await call("PUT", base + f"/{target}", expected=403, json={"role": "INSTRUCTOR"})
    await call("PUT", base + "/999999", actor="admin", expected=404, json={"role": "INSTRUCTOR"})
    await call(
        "PUT",
        base + f"/{users['student']}",
        actor="admin",
        expected=409,
        json={"role": "INSTRUCTOR"},
    )
    await call("PUT", base + f"/{target}", actor="admin", expected=422, json={"role": "ADMIN"})
    await call("PUT", base + f"/{target}", actor="admin", json={"role": "ASSISTANT"})
    await call("GET", f"/courses/{cid}/enrollments", actor="other", expected=403)
    await call("PUT", base + f"/{target}", actor="admin", json={"role": "INSTRUCTOR"})
    await call("PUT", base + f"/{target}", actor="admin", json={"role": "INSTRUCTOR"})
    assert len(await call("GET", base)) == 1
    assert await call("GET", f"/courses/{cid}/enrollments", actor="other") == []
    await call("DELETE", base + f"/{target}", actor="other", expected=403)
    await call("DELETE", base + f"/{target}", actor="admin")
    await call("GET", f"/courses/{cid}", actor="other", expected=403)
    await call("DELETE", base + f"/{target}", actor="admin", expected=404)


async def test_concurrent_enrollment_and_transition(api):
    call, _, users, tokens, client = api
    cid, _ = await published_course(call)
    url = f"/api/v1/courses/{cid}/enrollments"
    headers = {"Authorization": "Bearer " + tokens["student"]["access_token"]}
    rows = await asyncio.gather(*[client.post(url, json={}, headers=headers) for _ in range(2)])
    assert sorted(r.status_code for r in rows) == [201, 409]
    headers = {"Authorization": "Bearer " + tokens["owner"]["access_token"]}
    rows = await asyncio.gather(
        *[
            client.patch(url + f"/{users['student']}", json={"status": "ACTIVE"}, headers=headers)
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in rows) == [200, 409]


async def test_enrollment_audit_failure_is_atomic(api, monkeypatch):
    call, engine, _, _, _ = api
    cid, _ = await published_course(call)

    async def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditRepository, "append_log", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await call("POST", f"/courses/{cid}/enrollments", actor="student", expected=201, json={})
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT COUNT(*) FROM enrollments")) == 0


async def test_demo_seed_idempotent_login_and_preserves_progress(api):
    _, engine, _, _, client = api
    async with engine.begin() as conn:
        first = await seed_demo(conn)
    async with engine.begin() as conn:
        second = await seed_demo(conn)
    assert first == second
    for name in ("admin", "instructor", "student"):
        login = await client.post(
            "/api/v1/auth/login", json={"login": "demo_" + name, "password": DEMO_PASSWORD}
        )
        assert login.status_code == 200
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer " + login.json()["data"]["access_token"]},
        )
        assert me.json()["data"]["roles"] == [name.upper()]
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE enrollments SET status='SUSPENDED' WHERE course_id=:id"),
            {"id": first["course_id"]},
        )
        await seed_demo(conn)
    async with engine.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT status FROM enrollments WHERE course_id=:id"),
                {"id": first["course_id"]},
            )
            == "SUSPENDED"
        )
    with pytest.raises(ValueError, match="differs"):
        async with engine.begin() as conn:
            await seed_demo(conn, "a-different-password")


async def test_staff_revoked_while_course_write_waits_cannot_use_old_snapshot(api):
    call, engine, users, tokens, client = api
    cid = (await new_course(call))["id"]
    target = users["other"]
    await call("PUT", f"/courses/{cid}/staff/{target}", actor="admin", json={"role": "INSTRUCTOR"})
    async with engine.connect() as conn:
        await conn.execute(text("SELECT id FROM courses WHERE id=:id FOR UPDATE"), {"id": cid})
        pending = asyncio.create_task(
            client.put(
                f"/api/v1/courses/{cid}",
                json={"code": "SHOULD_NOT_CHANGE", "title": "Denied"},
                headers={"Authorization": "Bearer " + tokens["other"]["access_token"]},
            )
        )
        try:
            await asyncio.sleep(0.15)
            assert not pending.done()
            await conn.execute(
                text("DELETE FROM course_staff WHERE course_id=:id AND user_id=:uid"),
                {"id": cid, "uid": target},
            )
            await conn.commit()
            assert (await asyncio.wait_for(pending, 5)).status_code == 403
        finally:
            await conn.rollback()
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
