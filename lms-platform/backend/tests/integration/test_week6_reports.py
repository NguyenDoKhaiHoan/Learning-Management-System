"""Course reports and durable private CSV exports on disposable MySQL."""

import asyncio
import csv
from io import StringIO
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.jobs.processors import exports as export_processor
from src.jobs.processors.exports import process_exports
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.reporting_export.application.reports import CourseReports
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week4_grading import submitted

pytestmark = pytest.mark.integration


def config(api):
    return api[-1]._transport.app.state.settings


def export_body(cid=None, kind="GRADEBOOK", **filters):
    return {"request_id": str(uuid4()), "kind": kind, "course_id": cid, "filters": filters}


async def download(api, job, actor="owner"):
    _, _, _, tokens, client = api
    return await client.get(
        f"/api/v1/exports/{job['id']}/content",
        headers={"Authorization": "Bearer " + tokens[actor]["access_token"]},
    )


async def test_reports_filter_totals_pagination_published_defaults_and_staff_scope(api):
    call, engine, cid, _, _, _, grade = await submitted(api)
    _, _, users, _, _ = api
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO enrollments(course_id,student_id,status) "
                "VALUES (:cid,:student,'PENDING')"
            ),
            {"cid": cid, "student": users["other"]},
        )
    modules = await call("GET", f"/courses/{cid}/modules")
    lesson = modules[0]["lessons"][0]["id"]
    await call(
        "PUT",
        f"/courses/{cid}/lessons/{lesson}/progress",
        actor="student",
        json={"status": "COMPLETED"},
    )
    page = await call("GET", f"/reports/courses/{cid}/learners?limit=1")
    assert len(page["items"]) == 1 and page["total"] == 2
    assert page["totals"]["active_learners"] == page["totals"]["completed_learners"] == 1
    assert float(page["totals"]["average_progress"]) == 50
    second = await call("GET", f"/reports/courses/{cid}/learners?limit=1&offset=1")
    assert second["items"][0]["student_id"] != page["items"][0]["student_id"]
    pending = await call("GET", f"/reports/courses/{cid}/learners?enrollment_status=PENDING")
    assert pending["total"] == 1 and pending["items"][0]["username"] == "other"
    assert (await call("GET", f"/reports/courses/{cid}/learners?search=absent"))["total"] == 0
    assert (await call("GET", f"/reports/courses/{cid}/gradebook"))["total"] == 0
    assert (await call("GET", f"/reports/courses/{cid}/gradebook?grade_status=DRAFT"))["total"] == 1
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    grades = await call(
        "GET", f"/reports/courses/{cid}/gradebook?assessment_type=EXAM&search=student"
    )
    assert grades["total"] == 1 and grades["items"][0]["grade_id"] == str(grade["id"])
    assert "password" not in str(grades) and "question_snapshot" not in str(grades)
    for actor in ("other", "student", None):
        await call(
            "GET",
            f"/reports/courses/{cid}/learners",
            actor=actor,
            expected=401 if actor is None else 403,
        )
        await call(
            "GET",
            f"/reports/courses/{cid}/gradebook",
            actor=actor,
            expected=401 if actor is None else 403,
        )
    await call("GET", f"/reports/courses/{cid}/gradebook?grade_status=INVALID", expected=422)
    await call("GET", f"/reports/courses/{cid}/learners?limit=101", expected=422)
    await call(
        "PUT", f"/courses/{cid}/staff/{users['other']}", actor="admin", json={"role": "INSTRUCTOR"}
    )
    assert (await call("GET", f"/reports/courses/{cid}/gradebook", actor="other"))["total"] == 1
    await call("DELETE", f"/courses/{cid}/staff/{users['other']}", actor="admin")
    await call("GET", f"/reports/courses/{cid}/gradebook", actor="other", expected=403)


async def test_export_queue_retry_concurrent_workers_csv_and_download_audit(api):
    call, engine, cid, _, _, _, grade = await submitted(api)
    feedback = '=HYPERLINK("https://example.test","x")\nTiếng Việt, "quoted"'
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE gradebook_entries SET feedback=:feedback WHERE id=:id"),
            {"id": grade["id"], "feedback": feedback},
        )
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    body = export_body(cid, assessment_type="EXAM", search="student")
    job = await call("POST", "/exports", expected=202, json=body)
    assert job["status"] == "PENDING" and "location" not in job
    assert (await call("POST", "/exports", expected=202, json=body))["id"] == job["id"]
    await call("POST", "/exports", expected=409, json=body | {"filters": {"grade_status": "ALL"}})
    assert (await download(api, job)).status_code == 409
    assert (
        sum(
            await asyncio.gather(
                process_exports(engine, config(api)), process_exports(engine, config(api))
            )
        )
        == 1
    )
    ready = await call("GET", f"/exports/{job['id']}")
    assert ready["status"] == "READY" and ready["row_count"] == 1
    assert await process_exports(engine, config(api)) == 0
    response = await download(api, job)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["feedback"] == "'" + feedback
    assert rows[0]["grade_id"] == str(grade["id"]) and rows[0]["status"] == "PUBLISHED"
    assert float(rows[0]["score"]) == 10
    for actor in ("other", "admin"):
        await call("GET", f"/exports/{job['id']}", actor=actor, expected=404)
        assert (await download(api, job, actor)).status_code == 404
    assert (await download(api, job, "student")).status_code == 403
    assert (await call("GET", "/exports?limit=1"))["total"] == 1
    async with engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT COUNT(*) FROM audit_logs WHERE action='export.ready'"))
            == 1
        )
        assert (
            await conn.scalar(
                text("SELECT COUNT(*) FROM audit_logs WHERE action='export.download'")
            )
            == 1
        )


async def test_all_export_kinds_empty_filter_pending_cap_validation_and_permission_loss(api):
    call, engine, cid, _, _, _, _ = await submitted(api)
    for actor in ("other", "student"):
        await call("POST", "/exports", actor=actor, expected=403, json=export_body(cid))
    await call("POST", "/exports", expected=403, json=export_body(kind="OVERVIEW"))
    await call("POST", "/exports", expected=422, json=export_body())
    await call("POST", "/exports", expected=422, json=export_body(cid, enrollment_status="ACTIVE"))
    overview = await call(
        "POST", "/exports", actor="admin", expected=202, json=export_body(kind="OVERVIEW")
    )
    learner = await call(
        "POST",
        "/exports",
        expected=202,
        json=export_body(cid, "LEARNERS", enrollment_status="ACTIVE"),
    )
    empty = await call(
        "POST", "/exports", expected=202, json=export_body(cid, search="no-such-user")
    )
    await call("POST", "/exports", expected=202, json=export_body(cid))
    await call("POST", "/exports", expected=409, json=export_body(cid))
    assert await process_exports(engine, config(api)) == 4
    assert (await call("GET", f"/exports/{empty['id']}"))["row_count"] == 0
    assert (await call("GET", f"/exports/{learner['id']}"))["row_count"] == 1
    assert (await call("GET", f"/exports/{overview['id']}", actor="admin"))["row_count"] == 1
    pending = await call("POST", "/exports", expected=202, json=export_body(cid))
    await call("DELETE", "/roles/INSTRUCTOR/permissions/course.read", actor="admin")
    assert (await download(api, learner)).status_code == 403
    assert await process_exports(engine, config(api)) == 1
    await call("PUT", "/roles/INSTRUCTOR/permissions/course.read", actor="admin")
    failed = await call("GET", f"/exports/{pending['id']}")
    assert failed["status"] == "FAILED" and failed["error_code"] == "ACCESS_REVOKED"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE courses SET created_by=(SELECT id FROM users WHERE username='other') "
                "WHERE id=:id"
            ),
            {"id": cid},
        )
    assert (await download(api, learner)).status_code == 403


async def test_export_audit_failure_rolls_back_queue_cleans_file_and_row_limit(api, monkeypatch):
    call, engine, cid, _, _, _, grade = await submitted(api)
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    original = AuditRepository.append_log
    failures = {"export.request", "export.ready"}

    async def fail(self, **kwargs):
        if kwargs["action"] in failures:
            raise RuntimeError("audit unavailable")
        return await original(self, **kwargs)

    monkeypatch.setattr(AuditRepository, "append_log", fail)
    with pytest.raises(RuntimeError):
        await call("POST", "/exports", expected=202, json=export_body(cid))
    assert (await call("GET", "/exports"))["total"] == 0
    failures.remove("export.request")
    job = await call("POST", "/exports", expected=202, json=export_body(cid))
    assert await process_exports(engine, config(api)) == 1
    assert (await call("GET", f"/exports/{job['id']}"))["error_code"] == "EXPORT_FAILED"
    assert list((config(api).private_storage_root / "exports").glob("*.csv")) == []
    failures.clear()
    monkeypatch.setattr(export_processor, "MAX_EXPORT_ROWS", 0)
    large = await call("POST", "/exports", expected=202, json=export_body(cid))
    await process_exports(engine, config(api))
    assert (await call("GET", f"/exports/{large['id']}"))["error_code"] == "ROW_LIMIT"


async def test_report_reads_grade_revised_while_waiting_for_course_lock(api, monkeypatch):
    call, engine, cid, _, _, _, grade = await submitted(api)
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    authenticated = asyncio.Event()
    original = CourseReports.scope

    async def signal(self, *args, **kwargs):
        authenticated.set()
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(CourseReports, "scope", signal)
    async with engine.begin() as conn:
        await conn.execute(text("SELECT id FROM courses WHERE id=:id FOR UPDATE"), {"id": cid})
        request = asyncio.create_task(call("GET", f"/reports/courses/{cid}/gradebook"))
        await asyncio.wait_for(authenticated.wait(), timeout=10)
        await conn.execute(
            text(
                "UPDATE gradebook_entries SET status='DRAFT',published_at=NULL,version=version+1 "
                "WHERE id=:id"
            ),
            {"id": grade["id"]},
        )
    assert (await asyncio.wait_for(request, timeout=10))["total"] == 0


async def test_export_serialization_does_not_block_api_and_cancelled_job_restarts(api, monkeypatch):
    call, engine, cid, _, _, _, _ = await submitted(api)
    job = await call("POST", "/exports", expected=202, json=export_body(cid, "LEARNERS"))
    started, release = Event(), Event()
    original = export_processor.write_csv

    def pause(*args):
        started.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(export_processor, "write_csv", pause)
    worker = asyncio.create_task(process_exports(engine, config(api)))
    try:
        assert await asyncio.to_thread(started.wait, 10)
        # A different API actor can read data while the file writer is paused.
        await asyncio.wait_for(call("GET", "/users", actor="admin"), timeout=2)
        worker.cancel()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert (await call("GET", f"/exports/{job['id']}"))["status"] == "PENDING"
    assert list((config(api).private_storage_root / "exports").glob("*.csv")) == []
    monkeypatch.setattr(export_processor, "write_csv", original)
    assert await process_exports(engine, config(api)) == 1
    assert (await call("GET", f"/exports/{job['id']}"))["status"] == "READY"
