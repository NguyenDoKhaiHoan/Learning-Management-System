"""Admin account operations and dashboard scope through HTTP on real MySQL."""

import pytest
from sqlalchemy import text

from src.modules.audit_security.infrastructure.repository import AuditRepository
from tests.integration.test_week2_mysql import PASSWORD, new_content, new_course
from tests.integration.test_week2_mysql import api as api

pytestmark = pytest.mark.integration


async def test_admin_accounts_search_pagination_roles_status_and_no_credentials(api):
    call, engine, users, _, client = api
    for actor in ("owner", "student", None):
        await call("GET", "/users", actor=actor, expected=401 if actor is None else 403)
        await call(
            "POST",
            "/users",
            actor=actor,
            expected=401 if actor is None else 403,
            json={
                "email": "new@example.com",
                "username": "new_user",
                "password": PASSWORD,
                "roles": ["STUDENT"],
            },
        )
    page = await call("GET", "/users?limit=2", actor="admin")
    assert page["total"] == 4 and len(page["items"]) == 2
    second = await call("GET", "/users?limit=2&offset=2", actor="admin")
    assert not {u["id"] for u in page["items"]} & {u["id"] for u in second["items"]}
    assert "password" not in str(page) and "token" not in str(page)
    await call("GET", "/users?limit=101", actor="admin", expected=422)
    body = {
        "email": "New@Example.com",
        "username": "new_user",
        "password": PASSWORD,
        "roles": ["STUDENT"],
        "status": "ACTIVE",
    }
    created = await call("POST", "/users", actor="admin", expected=201, json=body)
    assert created["email"] == "new@example.com" and created["roles"] == ["STUDENT"]
    assert "password" not in str(created)
    uid = created["id"]
    await call("POST", "/users", actor="admin", expected=409, json=body)
    await call("POST", "/users", actor="admin", expected=422, json=body | {"roles": ["UNKNOWN"]})
    await call("POST", "/users", actor="admin", expected=422, json=body | {"password": "short"})
    filtered = await call("GET", "/users?search=new_user", actor="admin")
    assert filtered["total"] == 1 and filtered["items"][0]["id"] == uid
    edited = await call(
        "PUT",
        f"/users/{uid}",
        actor="admin",
        json={"username": "edited_user", "email": "edited@example.com"},
    )
    assert edited["username"] == "edited_user"
    await call(
        "PUT",
        f"/users/{uid}",
        actor="student",
        expected=403,
        json={"username": "illegal", "email": "illegal@example.com"},
    )
    await call("PUT", f"/users/{uid}/roles/INSTRUCTOR", actor="admin", expected=201)
    assert await call("GET", f"/users/{uid}/roles", actor="admin") == ["INSTRUCTOR", "STUDENT"]
    await call("DELETE", f"/users/{uid}/roles/STUDENT", actor="admin")
    await call("PATCH", f"/auth/users/{uid}/status", actor="admin", json={"status": "LOCKED"})
    locked = await call("GET", "/users?status=LOCKED", actor="admin")
    assert locked["total"] == 1 and locked["items"][0]["id"] == uid
    response = await client.post(
        "/api/v1/auth/login", json={"login": "edited_user", "password": PASSWORD}
    )
    assert response.status_code == 401
    async with engine.connect() as conn:
        actions = set((await conn.execute(text("SELECT action FROM audit_logs"))).scalars())
        assert {
            "account.create",
            "account.update",
            "account.status",
            "role.assign",
            "role.revoke",
        } <= actions


async def test_dashboard_reports_scope_global_totals_and_staff_assignment(api):
    call, engine, users, _, _ = api
    first = (await new_course(call))["id"]
    await new_content(call, first)
    await call("POST", f"/courses/{first}/status", json={"status": "PUBLISHED"})
    second = (await new_course(call, code="OTHER", actor="other"))["id"]
    overview = await call("GET", "/reports/overview?limit=1", actor="admin")
    assert overview["total_courses"] == overview["totals"]["total_courses"] == 2
    assert overview["totals"]["total_users"] == 4 and len(overview["courses"]) == 1
    assert overview["totals"]["published_courses"] == 1
    report = await call("GET", "/dashboard/instructor")
    assert [c["id"] for c in report["courses"]] == [first]
    assert report["totals"]["total_courses"] == 1
    for path in ("/users", "/reports/overview", "/dashboard/instructor"):
        await call("GET", path, actor="student", expected=403)
    await call("GET", "/reports/overview", actor="owner", expected=403)
    await call("GET", "/dashboard/instructor", actor="admin", expected=403)
    await call(
        "PUT",
        f"/courses/{second}/staff/{users['owner']}",
        actor="admin",
        json={"role": "INSTRUCTOR"},
    )
    assert (await call("GET", "/dashboard/instructor"))["total_courses"] == 2
    await call("DELETE", f"/courses/{second}/staff/{users['owner']}", actor="admin")
    assert (await call("GET", "/dashboard/instructor"))["total_courses"] == 1
    await call(
        "POST", f"/courses/{first}/enrollments", json={"student_id": users["student"]}, expected=201
    )
    owner_notifications = await call("GET", "/notifications", actor="owner")
    assert owner_notifications["unread"] >= 1
    assert any(item["type"] == "ENROLLMENT_REQUEST" for item in owner_notifications["items"])
    await call(
        "PATCH", f"/courses/{first}/enrollments/{users['student']}", json={"status": "ACTIVE"}
    )
    student_notifications = await call("GET", "/notifications", actor="student")
    status_notice = next(
        item for item in student_notifications["items"] if item["type"] == "ENROLLMENT_STATUS"
    )
    await call("PATCH", f"/notifications/{status_notice['id']}/read", actor="student")
    assert (await call("GET", "/notifications/unread-count", actor="student"))["unread"] == 0
    assert (await call("GET", "/reports/overview", actor="admin"))["totals"][
        "active_enrollments"
    ] == 1
    await call("DELETE", f"/courses/{second}", actor="other")
    assert (await call("GET", "/reports/overview", actor="admin"))["totals"]["total_courses"] == 1
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "DELETE rp FROM role_permissions rp JOIN roles r ON r.id=rp.role_id "
                "JOIN permissions p ON p.id=rp.permission_id "
                "WHERE r.code='INSTRUCTOR' AND p.code='course.read'"
            )
        )
    await call("GET", "/dashboard/instructor", expected=403)


async def test_account_audit_failure_rolls_back_user_and_role_assignments(api, monkeypatch):
    call, engine, _, _, _ = api
    original = AuditRepository.append_log

    async def fail(self, **kwargs):
        if kwargs["action"] == "account.create":
            raise RuntimeError("audit unavailable")
        return await original(self, **kwargs)

    monkeypatch.setattr(AuditRepository, "append_log", fail)
    body = {
        "email": "rollback@example.com",
        "username": "rollback_user",
        "password": PASSWORD,
        "roles": ["INSTRUCTOR", "STUDENT"],
    }
    with pytest.raises(RuntimeError):
        await call("POST", "/users", actor="admin", expected=201, json=body)
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT COUNT(*) FROM users")) == 4
        assert await conn.scalar(text("SELECT COUNT(*) FROM user_roles")) == 4
    monkeypatch.setattr(AuditRepository, "append_log", original)
    await call("POST", "/users", actor="admin", expected=201, json=body)
