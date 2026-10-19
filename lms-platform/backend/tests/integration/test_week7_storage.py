"""Scanned publication, legacy quarantine, cleanup and integrity on MySQL."""

import asyncio
import hashlib

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from src.jobs.processors.file_scanning import scan_pending_files
from src.modules.assignment.presentation import router as assignment_router
from src.modules.file_management.presentation import router as file_router
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_content, new_course
from tests.integration.test_week3_assignments import assignment_body, ready_course

pytestmark = pytest.mark.integration


async def test_lesson_scan_quarantine_cleanup_and_digest_check(api, monkeypatch):
    call, engine, _, tokens, client = api
    cid = (await new_course(call))["id"]
    mid, lid = await new_content(call, cid)
    base = f"/courses/{cid}/modules/{mid}/lessons/{lid}/resources"
    payload = b"%PDF-1.7\nscanned lesson"
    uploaded = await call(
        "POST",
        base + "/file",
        expected=201,
        content=payload,
        headers={"Content-Type": "application/pdf", "X-File-Name": "lesson.pdf"},
    )
    path = base + f"/{uploaded['id']}/content"
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text("""SELECT location,scan_status,scan_engine,scanned_at,sha256
                     FROM lesson_resources WHERE id=:id"""),
                {"id": uploaded["id"]},
            )
        ).mappings().one()
    assert row["scan_status"] == "CLEAN" and row["scan_engine"] == "development-eicar"
    assert row["scanned_at"] is not None and row["sha256"] == hashlib.sha256(payload).hexdigest()
    response = await client.get(
        "/api/v1" + path,
        headers={"Authorization": "Bearer " + tokens["owner"]["access_token"]},
    )
    assert response.status_code == 200 and response.content == payload
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE lesson_resources SET scan_status='PENDING' WHERE id=:id"),
            {"id": uploaded["id"]},
        )
    await call("GET", path, expected=409)
    assert await scan_pending_files(engine, client._transport.app.state.settings) == 1
    assert (await client.get(
        "/api/v1" + path,
        headers={"Authorization": "Bearer " + tokens["owner"]["access_token"]},
    )).status_code == 200
    stored = client._transport.app.state.settings.private_storage_root / row["location"]
    stored.write_bytes(b"%PDF-1.7\ntampered")
    await call("GET", path, expected=409)
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE lesson_resources SET scan_status='PENDING' WHERE id=:id"),
            {"id": uploaded["id"]},
        )
    assert await scan_pending_files(engine, client._transport.app.state.settings) == 1
    async with engine.connect() as connection:
        assert await connection.scalar(
            text("SELECT scan_status FROM lesson_resources WHERE id=:id"),
            {"id": uploaded["id"]},
        ) == "REJECTED"

    before = set(client._transport.app.state.settings.private_storage_root.rglob("*.*"))

    async def infected(*_args):
        raise HTTPException(422, "File was rejected by the security scanner")

    monkeypatch.setattr(file_router, "scan_file", infected)
    await call(
        "POST",
        base + "/file",
        expected=422,
        content=payload,
        headers={"Content-Type": "application/pdf", "X-File-Name": "infected.pdf"},
    )
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT COUNT(*) FROM lesson_resources")) == 1
    assert set(client._transport.app.state.settings.private_storage_root.rglob("*.*")) == before


async def test_submission_scan_failure_has_no_submission_or_file(api, monkeypatch):
    call, engine, users, tokens, client = api
    cid = await ready_course(call, engine, users)
    base = f"/courses/{cid}/assignments"
    assignment = await call("POST", base, expected=201, json=assignment_body())
    await call("POST", base + f"/{assignment['id']}/status", json={"status": "PUBLISHED"})

    async def unavailable(*_args):
        raise HTTPException(503, "File scanner unavailable; retry later")

    monkeypatch.setattr(assignment_router, "scan_file", unavailable)
    await call(
        "POST",
        base + f"/{assignment['id']}/submissions/file",
        actor="student",
        expected=503,
        content=b"%PDF-1.7\nprivate answer",
        headers={"Content-Type": "application/pdf", "X-File-Name": "answer.pdf"},
    )
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT COUNT(*) FROM assignment_submissions")) == 0
        assert await connection.scalar(text("SELECT COUNT(*) FROM submission_files")) == 0
    assert not list(
        (client._transport.app.state.settings.private_storage_root / "submissions").rglob("*.*")
    )

    async def cancelled(*_args):
        raise asyncio.CancelledError

    monkeypatch.setattr(assignment_router, "scan_file", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await client.post(
            "/api/v1" + base + f"/{assignment['id']}/submissions/file",
            content=b"%PDF-1.7\ncancelled answer",
            headers={
                "Authorization": "Bearer " + tokens["student"]["access_token"],
                "Content-Type": "application/pdf",
                "X-File-Name": "cancelled.pdf",
            },
        )
    assert not list(
        (client._transport.app.state.settings.private_storage_root / "submissions").rglob("*.*")
    )
