"""Week 2 acceptance checks through HTTP and real SQL in disposable databases."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from src.config.config import Settings
from src.core.database.database import build_engine
from src.main import create_app
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.identity_access.application.passwords import hash_password
from src.modules.identity_access.application.sessions import token_digest
from src.modules.identity_access.domain.enums import UserStatus
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.user_role.infrastructure.repository import RoleRepository

pytestmark = pytest.mark.integration
PASSWORD = "week2-acceptance-password"


@pytest.fixture
async def api():
    raw = os.getenv("MYSQL_TEST_ADMIN_URL")
    if not raw:
        pytest.skip("Set MYSQL_TEST_ADMIN_URL for MySQL integration tests")
    url = make_url(raw)
    database = "lms_test_" + uuid4().hex
    admin = create_async_engine(url.set(database=None), isolation_level="AUTOCOMMIT")
    config = Settings(
        _env_file=None,
        app_env="test",
        db_host_override=None,
        database_url=url.set(database=database).render_as_string(hide_password=False),
        jwt_secret="week2-test-secret-" + uuid4().hex,
    )
    engine = build_engine(config)
    async with admin.connect() as conn:
        await conn.execute(text(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4"))
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[2],
            env={
                **os.environ,
                "DATABASE_URL": config.database_url.get_secret_value(),
                "JWT_SECRET": config.jwt_secret.get_secret_value(),
                "DB_HOST_OVERRIDE": "",
            },
            capture_output=True,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stderr.decode()
        users = {}
        async with engine.begin() as conn:
            roles = RoleRepository(conn)
            role_ids = {
                code: await roles.create_role(code, code)
                for code in ("ADMIN", "INSTRUCTOR", "STUDENT")
            }
            for permission in ("course.read", "course.write", "course.publish"):
                pid = await roles.create_permission(permission)
                for role in ("ADMIN", "INSTRUCTOR", "STUDENT"):
                    if role != "STUDENT" or permission == "course.read":
                        await roles.grant_permission(role_ids[role], pid)
            password_hash = hash_password(PASSWORD)
            for name, role in (
                ("admin", "ADMIN"),
                ("owner", "INSTRUCTOR"),
                ("other", "INSTRUCTOR"),
                ("student", "STUDENT"),
            ):
                uid = await IdentityRepository(conn).create_user(
                    email=name + "@example.com",
                    username=name,
                    hashed_password=password_hash,
                    status=UserStatus.ACTIVE,
                )
                users[name] = uid
                await roles.assign_role(uid, role_ids[role])
        app = create_app(config)
        app.state.db_engine = engine
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {}
            tokens = {}
            for name in users:
                response = await client.post(
                    "/api/v1/auth/login", json={"login": name, "password": PASSWORD}
                )
                assert response.status_code == 200
                tokens[name] = response.json()["data"]
                headers[name] = {"Authorization": "Bearer " + tokens[name]["access_token"]}

            async def call(method, path, *, actor="owner", expected=200, **kwargs):
                response = await client.request(
                    method, "/api/v1" + path, headers=headers.get(actor, {}), **kwargs
                )
                assert response.status_code == expected, response.text
                assert response.headers["x-trace-id"] == response.json()["trace_id"]
                return response.json().get("data")

            yield call, engine, users, tokens, client
    finally:
        await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(text(f"DROP DATABASE `{database}`"))
        await admin.dispose()


async def new_course(call, code="COURSE", actor="owner"):
    return await call(
        "POST",
        "/courses",
        actor=actor,
        expected=201,
        json={"code": code, "title": "Course 🎓", "description": "Description"},
    )


async def new_content(call, cid):
    base = f"/courses/{cid}/modules"
    module = await call("POST", base, expected=201, json={"title": "Module"})
    lesson = await call(
        "POST",
        base + f"/{module['id']}/lessons",
        expected=201,
        json={"title": "Lesson", "lesson_type": "ARTICLE", "content": "Text"},
    )
    return module["id"], lesson["id"]


async def test_refresh_rotation_reuse_logout_and_expiry(api):
    call, engine, users, tokens, client = api
    old = tokens["owner"]["refresh_token"]
    rotated = await call("POST", "/auth/refresh", actor=None, json={"refresh_token": old})
    assert rotated["refresh_token"] != old
    await call("POST", "/auth/refresh", expected=401, json={"refresh_token": old})
    await call(
        "POST", "/auth/refresh", expected=401, json={"refresh_token": rotated["refresh_token"]}
    )
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT token_hash, revoked_at FROM refresh_tokens WHERE user_id=:id"),
                {"id": users["owner"]},
            )
        ).all()
        assert all(row.revoked_at is not None for row in rows)
        assert token_digest(old) in {row.token_hash for row in rows}
        assert old not in {row.token_hash for row in rows}
        assert (
            await conn.scalar(
                text("SELECT COUNT(*) FROM security_events WHERE event_type='TOKEN_REUSE_DETECTED'")
            )
            >= 1
        )
    fresh = (
        await client.post("/api/v1/auth/login", json={"login": "owner", "password": PASSWORD})
    ).json()["data"]
    await call("POST", "/auth/logout", actor=None, json={"refresh_token": fresh["refresh_token"]})
    await call("POST", "/auth/logout", actor=None, json={"refresh_token": fresh["refresh_token"]})
    await call(
        "POST", "/auth/refresh", expected=401, json={"refresh_token": fresh["refresh_token"]}
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE refresh_tokens SET created_at=UTC_TIMESTAMP()-INTERVAL 2 DAY,"
                " expires_at=UTC_TIMESTAMP()-INTERVAL 1 DAY WHERE user_id=:id"
            ),
            {"id": users["other"]},
        )
    await call(
        "POST",
        "/auth/refresh",
        expected=401,
        json={"refresh_token": tokens["other"]["refresh_token"]},
    )
    await call("POST", "/auth/refresh", expected=401, json={"refresh_token": "x" * 64})
    await call("POST", "/auth/refresh", expected=422, json={"refresh_token": "short"})


async def test_account_status_and_role_permission_changes_are_live(api):
    call, engine, users, tokens, _ = api
    uid = users["other"]
    await call(
        "PATCH",
        f"/auth/users/{uid}/status",
        actor="student",
        expected=403,
        json={"status": "LOCKED"},
    )
    await call(
        "PATCH", "/auth/users/999999/status", actor="admin", expected=404, json={"status": "LOCKED"}
    )
    await call("PATCH", f"/auth/users/{uid}/status", actor="admin", json={"status": "LOCKED"})
    await call("GET", "/auth/me", actor="other", expected=401)
    await call("POST", "/auth/login", expected=401, json={"login": "other", "password": PASSWORD})
    await call("PATCH", f"/auth/users/{uid}/status", actor="admin", json={"status": "ACTIVE"})
    await call(
        "POST",
        "/auth/refresh",
        expected=401,
        json={"refresh_token": tokens["other"]["refresh_token"]},
    )
    await call("GET", "/permissions", actor="student", expected=403)
    assert len(await call("GET", "/permissions", actor="admin")) == 3
    assert len(await call("GET", "/roles", actor="admin")) == 3
    path = "/roles/INSTRUCTOR/permissions/course.write"
    await call("DELETE", path, actor="admin")
    await call("POST", "/courses", expected=403, json={"code": "NO", "title": "Denied"})
    await call("PUT", path, actor="admin")
    await call("PUT", path, actor="admin")
    assert "course.write" in await call("GET", "/roles/INSTRUCTOR/permissions", actor="admin")
    await new_course(call)
    await call("PUT", "/roles/UNKNOWN/permissions/course.write", actor="admin", expected=404)
    await call("PUT", "/roles/ADMIN/permissions/unknown", actor="admin", expected=422)
    role_path = f"/users/{uid}/roles/INSTRUCTOR"
    await call("DELETE", role_path, actor="admin")
    await call(
        "POST", "/courses", actor="other", expected=403, json={"code": "NO", "title": "Denied"}
    )
    await call("PUT", role_path, actor="admin", expected=201)
    await call("PUT", role_path, actor="admin", expected=409)
    await call("DELETE", f"/users/{uid}/roles/UNKNOWN", actor="admin", expected=404)
    await call("PUT", "/users/999999/roles/STUDENT", actor="admin", expected=404)
    async with engine.connect() as conn:
        actions = set((await conn.execute(text("SELECT action FROM audit_logs"))).scalars())
        assert {
            "account.status",
            "permission.grant",
            "permission.revoke",
            "role.assign",
            "role.revoke",
        } <= actions


async def test_course_crud_scope_validation_and_soft_delete(api):
    call, engine, users, _, _ = api
    await call("GET", "/courses", actor=None, expected=401)
    await call("POST", "/courses", actor="student", expected=403, json={"code": "X", "title": "No"})
    course = await new_course(call)
    cid = course["id"]
    assert isinstance(cid, str) and isinstance(course["created_by"], str)
    path = f"/courses/{cid}"
    await call("GET", path, actor="other", expected=403)
    await call("PUT", path, actor="other", expected=403, json={"code": "X", "title": "No"})
    await call("DELETE", path, actor="other", expected=403)
    assert await call("GET", "/courses", actor="other") == []
    assert (await call("GET", path, actor="admin"))["id"] == cid
    await call("POST", "/courses", expected=409, json={"code": "COURSE", "title": "Duplicate"})
    await call("POST", "/courses", expected=422, json={"code": "BAD", "title": "  "})
    await call(
        "POST",
        "/courses",
        expected=422,
        json={"code": "BAD", "title": "Title", "created_by": users["admin"]},
    )
    await call("GET", "/courses?limit=101", expected=422)
    await call("GET", "/courses/999999", expected=404)
    updated = await call("PUT", path, json={"code": "NEW", "title": "Updated"})
    assert updated["title"] == "Updated"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO course_staff (course_id,user_id,role) VALUES (:cid,:uid,'INSTRUCTOR')"
            ),
            {"cid": cid, "uid": users["other"]},
        )
    assert (await call("GET", path, actor="other"))["id"] == cid
    await call("PUT", path, actor="other", json={"code": "NEW", "title": "Staff edit"})
    await call("DELETE", path, actor="admin")
    await call("GET", path, expected=404)
    assert await call("GET", "/courses") == []


async def test_content_crud_order_publish_and_resource_boundaries(api):
    call, engine, _, _, _ = api
    cid = (await new_course(call))["id"]
    base = f"/courses/{cid}/modules"
    status = f"/courses/{cid}/status"
    await call("POST", status, json={"status": "PUBLISHED"}, expected=409)
    mid, lid = await new_content(call, cid)
    lesson_path = f"{base}/{mid}/lessons/{lid}"
    await call("GET", lesson_path, actor="other", expected=403)
    await call("PUT", base + f"/{mid}", json={"title": "Updated module"})
    await call(
        "PUT",
        lesson_path,
        json={"title": "Updated lesson", "lesson_type": "VIDEO", "content": "https://video"},
    )
    assert (await call("GET", lesson_path))["lesson_type"] == "VIDEO"
    second = await call("POST", base, expected=201, json={"title": "Second"})
    mid2 = second["id"]
    await call("POST", status, expected=409, json={"status": "PUBLISHED"})
    await call("GET", f"{base}/{mid2}/lessons/{lid}", expected=404)
    foreign = (await new_course(call, "FOREIGN"))["id"]
    await call("PUT", f"/courses/{foreign}/modules/{mid}", expected=404, json={"title": "No"})
    await call("PUT", base + "/order", json={"ids": [mid2, mid]})
    assert [row["id"] for row in await call("GET", base)] == [mid2, mid]
    for ids in ([mid], [mid, mid], [mid, "999999"]):
        await call("PUT", base + "/order", expected=422, json={"ids": ids})
    await call("DELETE", base + f"/{mid2}")
    await call("PUT", base + "/order", json={"ids": [mid]})
    third = await call("POST", base, expected=201, json={"title": "Third"})
    await call("DELETE", base + f"/{third['id']}")
    l2 = await call(
        "POST",
        f"{base}/{mid}/lessons",
        expected=201,
        json={"title": "Empty", "lesson_type": "ARTICLE"},
    )
    await call("POST", status, expected=409, json={"status": "PUBLISHED"})
    await call("PUT", f"{base}/{mid}/lessons/order", json={"ids": [l2["id"], lid]})
    assert (await call("GET", base))[0]["lessons"][0]["id"] == l2["id"]
    await call("DELETE", f"{base}/{mid}/lessons/{l2['id']}")
    await call("PUT", f"{base}/{mid}/lessons/order", json={"ids": [lid]})
    await call("GET", f"{base}/{mid}/lessons/{l2['id']}", expected=404)
    await call("POST", status, json={"status": "PUBLISHED"})
    await call("POST", status, expected=409, json={"status": "PUBLISHED"})
    await call("POST", base, expected=409, json={"title": "Frozen"})
    await call("DELETE", f"/courses/{cid}", expected=409)
    await call(
        "PUT",
        lesson_path,
        expected=409,
        json={"title": "Frozen", "lesson_type": "ARTICLE", "content": "Text"},
    )
    await call("POST", status, json={"status": "ARCHIVED"})
    await call("POST", status, expected=409, json={"status": "PUBLISHED"})
    await call("POST", status, json={"status": "DRAFT"})
    await call("DELETE", base + f"/{mid}")
    await call("GET", lesson_path, expected=404)
    await call("POST", status, expected=409, json={"status": "PUBLISHED"})
    async with engine.connect() as conn:
        actions = set((await conn.execute(text("SELECT action FROM audit_logs"))).scalars())
        assert {
            "course.published",
            "course.archived",
            "course.draft",
            "module.reorder",
            "lesson.reorder",
            "module.delete",
            "lesson.delete",
        } <= actions


async def test_student_reads_require_published_course_and_active_enrollment(api):
    call, engine, users, _, _ = api
    cid = (await new_course(call))["id"]
    mid, lid = await new_content(call, cid)
    path = f"/courses/{cid}/modules/{mid}/lessons/{lid}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO enrollments (course_id,student_id,status) VALUES (:cid,:uid,'ACTIVE')"
            ),
            {"cid": cid, "uid": users["student"]},
        )
    await call("GET", path, actor="student", expected=403)
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    assert (await call("GET", path, actor="student"))["content"] == "Text"
    assert len(await call("GET", "/courses", actor="student")) == 1
    for state in ("PENDING", "SUSPENDED"):
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE enrollments SET status=:state"), {"state": state})
        await call("GET", path, actor="student", expected=403)
        assert await call("GET", "/courses", actor="student") == []


async def test_concurrent_refresh_and_publish_are_serialized(api):
    call, _, _, tokens, client = api
    token = tokens["owner"]["refresh_token"]
    responses = await asyncio.gather(
        *[client.post("/api/v1/auth/refresh", json={"refresh_token": token}) for _ in range(2)]
    )
    assert sorted(r.status_code for r in responses) == [200, 401]
    fresh = next(r for r in responses if r.status_code == 200).json()["data"]["refresh_token"]
    await call("POST", "/auth/refresh", expected=401, json={"refresh_token": fresh})
    cid = (await new_course(call))["id"]
    await new_content(call, cid)
    responses = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/courses/{cid}/status",
                json={"status": "PUBLISHED"},
                headers={"Authorization": "Bearer " + tokens["owner"]["access_token"]},
            )
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]


async def test_audit_failure_rolls_back_business_write(api, monkeypatch):
    call, engine, _, _, _ = api
    cid = (await new_course(call))["id"]

    async def fail(*args, **kwargs):
        raise RuntimeError("simulated audit storage failure")

    monkeypatch.setattr(AuditRepository, "append_log", fail)
    with pytest.raises(RuntimeError, match="simulated audit"):
        await call("PUT", f"/courses/{cid}", json={"code": "CHANGED", "title": "Changed"})
    async with engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT code FROM courses WHERE id=:id"), {"id": cid})
            == "COURSE"
        )


async def test_publish_checks_content_committed_while_waiting_for_course_lock(api):
    call, engine, _, tokens, client = api
    cid = (await new_course(call))["id"]
    _, lid = await new_content(call, cid)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT id FROM courses WHERE id=:id FOR UPDATE"), {"id": cid})
        pending = asyncio.create_task(
            client.post(
                f"/api/v1/courses/{cid}/status",
                json={"status": "PUBLISHED"},
                headers={"Authorization": "Bearer " + tokens["owner"]["access_token"]},
            )
        )
        try:
            # Let the request authenticate and wait on the held parent lock.
            await asyncio.sleep(0.15)
            assert not pending.done()
            await conn.execute(text("UPDATE lessons SET content=NULL WHERE id=:id"), {"id": lid})
            await conn.commit()
            assert (await asyncio.wait_for(pending, 5)).status_code == 409
        finally:
            await conn.rollback()
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)


async def test_refresh_rejects_inactive_locked_and_deleted_users(api):
    call, engine, users, tokens, _ = api
    for name, state in (("owner", "INACTIVE"), ("other", "LOCKED"), ("student", "deleted")):
        async with engine.begin() as conn:
            if state == "deleted":
                await conn.execute(
                    text("UPDATE users SET deleted_at=UTC_TIMESTAMP(6) WHERE id=:id"),
                    {"id": users[name]},
                )
            else:
                await conn.execute(
                    text("UPDATE users SET status=:state WHERE id=:id"),
                    {"id": users[name], "state": state},
                )
        await call(
            "POST",
            "/auth/refresh",
            actor=None,
            expected=401,
            json={"refresh_token": tokens[name]["refresh_token"]},
        )
        await call(
            "POST",
            "/auth/login",
            actor=None,
            expected=401,
            json={"login": name, "password": PASSWORD},
        )
        await call("GET", "/auth/me", actor=name, expected=401)
