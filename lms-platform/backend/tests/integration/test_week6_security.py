"""Persistent security observations, scoped telemetry and human review boundaries."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.modules.audit_security.infrastructure.repository import AuditRepository
from tests.integration.test_week2_mysql import PASSWORD
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week4_exams import setup_exam

pytestmark = pytest.mark.integration


async def test_login_failed_unknown_locked_denied_and_security_projection(api):
    call, engine, users, tokens, client = api
    for username in ("owner", "unknown_user"):
        response = await client.post(
            "/api/v1/auth/login",
            json={"login": username, "password": "wrong-password"},
            headers={"X-Trace-ID": "login-failure-proof"},
        )
        assert response.status_code == 401
    await call(
        "GET",
        "/users?search=secret-query",
        actor="student",
        expected=403,
        headers={"X-Trace-ID": "denial-proof"},
    )
    await call("GET", "/audit/security-events", actor="owner", expected=403)
    await call(
        "PATCH", f"/auth/users/{users['other']}/status", actor="admin", json={"status": "LOCKED"}
    )
    response = await client.post(
        "/api/v1/auth/login", json={"login": "other", "password": PASSWORD}
    )
    assert response.status_code == 401
    failed = await call("GET", "/audit/security-events?event_type=LOGIN_FAILED", actor="admin")
    assert failed["total"] == 3 and any(r["actor_id"] is None for r in failed["items"])
    denied = await call("GET", "/audit/security-events?trace_id=denial-proof", actor="admin")
    assert denied["total"] == 1 and denied["items"][0]["actor_id"] == str(users["student"])
    assert denied["items"][0]["details"] == {
        "status": 403,
        "method": "GET",
        "route": "/api/v1/users",
    }
    events = await call("GET", "/audit/security-events?limit=100", actor="admin")
    assert {"LOGIN_SUCCEEDED", "LOGIN_FAILED", "ACCESS_DENIED", "ACCOUNT_LOCKED"} <= {
        r["event_type"] for r in events["items"]
    }
    assert "wrong-password" not in str(events) and "secret-query" not in str(events)
    assert tokens["student"]["access_token"] not in str(events)
    await call("GET", "/audit/security-events?event_type=UNKNOWN", actor="admin", expected=422)
    async with engine.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT COUNT(*) FROM security_events WHERE event_type='LOGIN_SUCCEEDED'")
            )
            == 4
        )


async def start(api):
    call, engine, cid, _, question, eid, _ = await setup_exam(api)
    await call("POST", f"/exams/{eid}/publish")
    attempt = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    return call, engine, cid, attempt, question


async def test_event_retry_concurrency_ownership_review_and_no_grade_penalty(api):
    call, engine, cid, attempt, question = await start(api)
    await call(
        "PUT",
        f"/attempts/{attempt['id']}/answers/{question['id']}",
        actor="student",
        json={"selected_option_ids": [question["options"][0]["id"]], "expected_version": 0},
    )
    _, _, _, tokens, client = api
    path = f"/attempts/{attempt['id']}/events"
    body = {"client_event_id": str(uuid4()), "event_type": "TAB_HIDDEN"}
    headers = {"Authorization": "Bearer " + tokens["student"]["access_token"]}
    responses = await asyncio.gather(
        *[client.post("/api/v1" + path, json=body, headers=headers) for _ in range(2)]
    )
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json()["data"]["id"] == responses[1].json()["data"]["id"]
    event = responses[0].json()["data"]
    await call(
        "POST", path, actor="student", expected=409, json=body | {"event_type": "WINDOW_BLUR"}
    )
    await call("POST", path, actor="owner", expected=403, json=body)
    await call("POST", path, actor="other", expected=403, json=body)
    await call("POST", path, actor="student", expected=422, json=body | {"answers": "private"})
    await call("GET", f"/courses/{cid}/attempt-events", actor="student", expected=403)
    await call("GET", f"/courses/{cid}/attempt-events", actor="other", expected=403)
    page = await call("GET", f"/courses/{cid}/attempt-events?status=PENDING&limit=1")
    assert page["total"] == 1 and page["items"][0]["review_status"] == "PENDING"
    assert "question_snapshot" not in str(page)
    review_path = f"/courses/{cid}/attempt-events/{event['id']}/review"
    review = {"expected_version": 1, "status": "DISMISSED", "note": "Accidental window switch"}
    await call("PATCH", review_path, actor="other", expected=403, json=review)
    await call("PATCH", review_path, expected=422, json=review | {"note": "  "})
    result = await call("PATCH", review_path, json=review)
    assert result["version"] == 2 and result["reviewed_by"] is not None
    await call("PATCH", review_path, expected=409, json=review)
    assert (await call("GET", f"/courses/{cid}/attempt-events?status=PENDING"))["total"] == 0
    submitted = await call("POST", f"/attempts/{attempt['id']}/submit", actor="student")
    assert submitted["server_version"] == 2
    retry = await call("POST", path, actor="student", expected=201, json=body)
    assert retry["id"] == event["id"]
    assert "review_note" not in retry and "reviewed_by" not in retry
    await call(
        "POST", path, actor="student", expected=409, json=body | {"client_event_id": str(uuid4())}
    )
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT COUNT(*) FROM attempt_events")) == 1
        assert (
            await conn.scalar(
                text("SELECT COUNT(*) FROM audit_logs WHERE action='security.review'")
            )
            == 1
        )
        assert (
            await conn.scalar(
                text("SELECT score FROM exam_attempts WHERE id=:id"), {"id": attempt["id"]}
            )
            == 10
        )


async def test_review_and_event_audit_failure_rollback_and_event_cap(api, monkeypatch):
    call, engine, cid, attempt, _ = await start(api)
    path = f"/attempts/{attempt['id']}/events"
    body = {"client_event_id": str(uuid4()), "event_type": "WINDOW_BLUR"}
    original = AuditRepository.append_log
    failed_actions = {"attempt.event", "security.review"}

    async def fail(self, **kwargs):
        if kwargs["action"] in failed_actions:
            raise RuntimeError("audit unavailable")
        return await original(self, **kwargs)

    monkeypatch.setattr(AuditRepository, "append_log", fail)
    with pytest.raises(RuntimeError):
        await call("POST", path, actor="student", expected=201, json=body)
    assert (await call("GET", f"/courses/{cid}/attempt-events"))["total"] == 0
    failed_actions.remove("attempt.event")
    event = await call("POST", path, actor="student", expected=201, json=body)
    with pytest.raises(RuntimeError):
        await call(
            "PATCH",
            f"/courses/{cid}/attempt-events/{event['id']}/review",
            json={"expected_version": 1, "status": "REVIEWED", "note": "Checked context"},
        )
    assert (await call("GET", f"/courses/{cid}/attempt-events"))["items"][0]["version"] == 1
    async with engine.begin() as conn:
        for _ in range(199):
            await conn.execute(
                text(
                    "INSERT INTO attempt_events(attempt_id,client_event_id,event_type,trace_id) "
                    "VALUES (:attempt,:client,'TAB_HIDDEN','cap-test')"
                ),
                {"attempt": attempt["id"], "client": str(uuid4())},
            )
    await call(
        "POST", path, actor="student", expected=409, json=body | {"client_event_id": str(uuid4())}
    )
