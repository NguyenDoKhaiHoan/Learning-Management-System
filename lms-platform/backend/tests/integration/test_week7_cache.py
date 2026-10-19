"""Real SQL invalidation across app caches, transactions and authorization scope."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.main import create_app
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.reporting_export.application.service import DashboardReports
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_course
from tests.integration.test_week6_reports import config

pytestmark = pytest.mark.integration


async def test_dashboard_hit_scope_pagination_and_committed_invalidation(api, monkeypatch):
    call, _, users, _, client = api
    first = (await new_course(call))["id"]
    other = (await new_course(call, code="OTHER", actor="other"))["id"]
    cache = client._transport.app.state.dashboard_cache
    original = DashboardReports.courses
    loads = 0

    async def count(self, *args, **kwargs):
        nonlocal loads
        loads += 1
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(DashboardReports, "courses", count)
    for _ in range(2):
        assert [c["id"] for c in (await call("GET", "/dashboard/instructor"))["courses"]] == [first]
    assert loads == 1 and cache.hits >= 1
    assert [c["id"] for c in (
        await call("GET", "/dashboard/instructor", actor="other")
    )["courses"]] == [other]
    admin = await call("GET", "/reports/overview?limit=1", actor="admin")
    assert admin["total_courses"] == 2 and len(admin["courses"]) == 1
    # Cached full data remains intact when a previous request paginates/mutates IDs.
    assert len((await call("GET", "/reports/overview?limit=2", actor="admin"))["courses"]) == 2
    await call("PUT", f"/courses/{other}/staff/{users['owner']}", actor="admin",
               json={"role": "INSTRUCTOR"})
    assert (await call("GET", "/dashboard/instructor"))["total_courses"] == 2
    await call("DELETE", f"/courses/{other}/staff/{users['owner']}", actor="admin")
    assert (await call("GET", "/dashboard/instructor"))["total_courses"] == 1
    await call("DELETE", "/roles/INSTRUCTOR/permissions/course.read", actor="admin")
    await call("GET", "/dashboard/instructor", expected=403)
    await call("PUT", "/roles/INSTRUCTOR/permissions/course.read", actor="admin")
    await call("PATCH", f"/auth/users/{users['owner']}/status", actor="admin",
               json={"status": "LOCKED"})
    await call("GET", "/dashboard/instructor", expected=401)


async def test_dashboard_other_process_cache_and_rollback_coherence(api):
    call, engine, _, tokens, _ = api
    cid = (await new_course(call))["id"]
    app = create_app(config(api))
    app.state.db_engine = engine
    headers = {"Authorization": "Bearer " + tokens["owner"]["access_token"]}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as second:
        async def title():
            response = await second.get("/api/v1/dashboard/instructor", headers=headers)
            assert response.status_code == 200
            return response.json()["data"]["courses"][0]["title"]

        original = await title()
        await call("GET", "/dashboard/instructor")  # Fill both independent caches.
        async with engine.connect() as connection:
            before = await connection.scalar(text("SELECT version FROM cache_versions WHERE id=1"))
            await connection.execute(text("UPDATE courses SET title='rolled back' WHERE id=:id"),
                                     {"id": cid})
            await AuditRepository(connection).append_log(
                actor_id=None, action="course.update", resource="course",
                resource_id=cid, trace_id="cache-test",
            )
            await connection.rollback()
            assert await connection.scalar(
                text("SELECT version FROM cache_versions WHERE id=1")
            ) == before
        assert await title() == original and app.state.dashboard_cache.hits == 1
        await call("PUT", f"/courses/{cid}",
                   json={"code": "COURSE", "title": "committed", "description": "new"})
        assert await title() == "committed"
        assert (await call("GET", "/dashboard/instructor"))["courses"][0]["title"] == "committed"
