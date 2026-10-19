"""Durable retry/backoff, partial file cleanup, restart and idempotency."""

import asyncio

import pytest
from sqlalchemy import text

from src.core.database.database import build_engine
from src.jobs.processors import exports as worker
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week3_assignments import ready_course
from tests.integration.test_week6_reports import config, export_body

pytestmark = pytest.mark.integration


async def make_job(api):
    call, engine, users, _, _ = api
    cid = await ready_course(call, engine, users)
    body = export_body(cid, "LEARNERS")
    job = await call("POST", "/exports", expected=202, json=body)
    return call, engine, body, job


async def make_due(engine, job):
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE export_jobs SET available_at=UTC_TIMESTAMP(6) WHERE id=:id"),
            {"id": job["id"]},
        )


async def test_export_transient_failure_backoff_restart_and_single_result(api, monkeypatch):
    call, engine, body, job = await make_job(api)
    original = worker.write_csv

    def interrupted(*args):
        original(*args)
        raise OSError("temporary storage failure")

    monkeypatch.setattr(worker, "write_csv", interrupted)
    assert await worker.process_exports(engine, config(api)) == 1
    pending = await call("GET", f"/exports/{job['id']}")
    assert pending["status"] == "PENDING" and pending["attempt_count"] == 1
    assert pending["error_code"] == "EXPORT_RETRY" and pending["completed_at"] is None
    assert list((config(api).private_storage_root / "exports").glob("*.csv")) == []
    # Backoff and request deduplication survive a fresh connection pool/worker.
    replacement = build_engine(config(api))
    try:
        assert await worker.process_exports(replacement, config(api)) == 0
        repeated = await call("POST", "/exports", expected=202, json=body)
        assert repeated["id"] == job["id"] and repeated["attempt_count"] == 1
        await make_due(engine, job)
        monkeypatch.setattr(worker, "write_csv", original)
        assert sum(await asyncio.gather(
            worker.process_exports(replacement, config(api)),
            worker.process_exports(engine, config(api)),
        )) == 1
    finally:
        await replacement.dispose()
    ready = await call("GET", f"/exports/{job['id']}")
    assert ready["status"] == "READY" and ready["attempt_count"] == 2
    assert ready["error_code"] is None
    assert len(list((config(api).private_storage_root / "exports").glob("*.csv"))) == 1
    async with engine.connect() as connection:
        for action in ("export.request", "export.retry", "export.ready"):
            assert await connection.scalar(
                text("SELECT COUNT(*) FROM audit_logs WHERE action=:action"), {"action": action}
            ) == 1


async def test_export_retry_exhaustion_and_concurrent_request_idempotency(api, monkeypatch):
    call, engine, body, job = await make_job(api)
    repeated = await asyncio.gather(*(
        call("POST", "/exports", expected=202, json=body) for _ in range(3)
    ))
    assert {row["id"] for row in repeated} == {job["id"]}
    await call("POST", "/exports", expected=409,
               json=body | {"filters": {"search": "different"}})

    def unavailable(*_):
        raise OSError("disk temporarily unavailable")

    monkeypatch.setattr(worker, "write_csv", unavailable)
    for attempt in range(1, 4):
        await make_due(engine, job)
        assert await worker.process_exports(engine, config(api)) == 1
        current = await call("GET", f"/exports/{job['id']}")
        assert current["attempt_count"] == attempt
        assert current["status"] == ("FAILED" if attempt == 3 else "PENDING")
    assert current["error_code"] == "EXPORT_FAILED" and current["completed_at"] is not None
    assert await worker.process_exports(engine, config(api)) == 0
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT COUNT(*) FROM export_jobs")) == 1
        assert await connection.scalar(
            text("SELECT COUNT(*) FROM audit_logs WHERE action='export.failed'")
        ) == 1


async def test_export_timeout_is_retryable_and_rechecks_scope(api, monkeypatch):
    call, engine, _, job = await make_job(api)
    settings = config(api).model_copy(update={"export_timeout_seconds": 1})
    original = worker.Exports.learners

    async def slow(*_, **__):
        await asyncio.sleep(10)

    monkeypatch.setattr(worker.Exports, "learners", slow)
    assert await worker.process_exports(engine, settings) == 1
    assert (await call("GET", f"/exports/{job['id']}"))["status"] == "PENDING"
    monkeypatch.setattr(worker.Exports, "learners", original)
    await make_due(engine, job)
    await call("DELETE", "/roles/INSTRUCTOR/permissions/course.read", actor="admin")
    assert await worker.process_exports(engine, settings) == 1
    await call("PUT", "/roles/INSTRUCTOR/permissions/course.read", actor="admin")
    failed = await call("GET", f"/exports/{job['id']}")
    assert failed["status"] == "FAILED" and failed["error_code"] == "ACCESS_REVOKED"
