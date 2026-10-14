"""AuthN/AuthZ, horizontal IDOR and private-file security on disposable MySQL."""

from datetime import UTC, datetime
from uuid import uuid4

import jwt
import pytest
from sqlalchemy import text

from src.core.security.jwt import create_access_token
from src.jobs.processors.exports import process_exports
from tests.integration.test_week2_mysql import PASSWORD, new_content, new_course
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week3_assignments import assignment_body
from tests.integration.test_week4_exams import setup_exam

pytestmark = [pytest.mark.integration, pytest.mark.security]


def authorization(token):
    return {"Authorization": "Bearer " + token}


def assert_error(response, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "details", "trace_id"}
    assert body["trace_id"] == response.headers["x-trace-id"]
    assert body["code"] == {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND"}[status]
    assert body["details"] == []
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"


async def peer_student(api, cid):
    call, _, _, _, client = api
    peer = await call(
        "POST",
        "/users",
        actor="admin",
        expected=201,
        json={
            "username": "peer",
            "email": "peer@example.com",
            "password": PASSWORD,
            "roles": ["STUDENT"],
        },
    )
    login = await client.post("/api/v1/auth/login", json={"login": "peer", "password": PASSWORD})
    assert login.status_code == 200
    headers = authorization(login.json()["data"]["access_token"])
    await call("POST", f"/courses/{cid}/enrollments", expected=201, json={"student_id": peer["id"]})
    await call("PATCH", f"/courses/{cid}/enrollments/{peer['id']}", json={"status": "ACTIVE"})

    async def peer_call(method, path, **kwargs):
        return await call(method, path, actor=None, headers=headers, **kwargs)

    return peer_call, headers


async def test_authentication_rejects_forged_expired_wrong_claims_and_refresh_tokens(api):
    _, engine, users, tokens, client = api
    config = client._transport.app.state.settings
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "sub": str(users["student"]),
        "iss": config.jwt_issuer,
        "aud": config.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": uuid4().hex,
        "token_type": "access",
    }
    secret = config.jwt_secret.get_secret_value()
    cases = {
        "missing": {},
        "wrong-scheme": {"Authorization": "Basic abc"},
        "malformed": authorization("not-a-jwt"),
        "refresh-as-access": authorization(tokens["student"]["refresh_token"]),
        "wrong-signature": authorization(jwt.encode(claims, "attacker-key" * 4, algorithm="HS256")),
        "unsigned": authorization(jwt.encode(claims, "", algorithm="none")),
    }
    for name, changes in {
        "expired": {"exp": now - 60},
        "future": {"nbf": now + 3600},
        "wrong-issuer": {"iss": "attacker"},
        "wrong-audience": {"aud": "attacker"},
        "wrong-token-type": {"token_type": "refresh"},
        "numeric-subject": {"sub": users["student"]},
        "oversized-subject": {"sub": "18446744073709551616"},
    }.items():
        cases[name] = authorization(jwt.encode(claims | changes, secret, algorithm="HS256"))
    cases["missing-expiry"] = authorization(
        jwt.encode(
            {key: value for key, value in claims.items() if key != "exp"},
            secret,
            algorithm="HS256",
        )
    )
    cases["unknown-user"] = authorization(create_access_token(999999, config))
    for name, headers in cases.items():
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401, name
        assert_error(response, 401)
        assert secret not in response.text
        assert tokens["student"]["refresh_token"] not in response.text
    # Extra role/permission claims signed by the trusted key still do not grant DB privileges.
    forged_roles = jwt.encode(
        claims | {"roles": ["ADMIN"], "permissions": ["course.write"]},
        secret,
        algorithm="HS256",
    )
    assert_error(await client.get("/api/v1/users", headers=authorization(forged_roles)), 403)
    async with engine.connect() as conn:
        assert await conn.scalar(
            text(
                "SELECT COUNT(*) FROM security_events WHERE event_type='ACCESS_DENIED' "
                "AND JSON_EXTRACT(details,'$.status')=401"
            )
        ) == len(cases)


@pytest.mark.parametrize(
    "actor", [None, "student", "other"], ids=["anonymous", "student", "outsider"]
)
async def test_privileged_route_matrix_denies_reads_and_writes_without_side_effects(api, actor):
    call, engine, cid, bid, _, eid, _ = await setup_exam(api)
    _, _, users, tokens, client = api
    requests = [
        ("GET", "/users", None),
        ("GET", "/roles", None),
        ("GET", "/permissions", None),
        ("GET", "/audit/logs", None),
        ("GET", "/audit/security-events", None),
        ("GET", "/reports/overview", None),
        ("GET", f"/courses/{cid}/grades", None),
        ("GET", f"/reports/courses/{cid}/learners", None),
        ("GET", f"/reports/courses/{cid}/gradebook", None),
        ("GET", f"/question-banks/{bid}/questions", None),
        ("GET", f"/courses/{cid}/attempt-events", None),
        ("PUT", f"/users/{users['student']}/roles/ADMIN", None),
        ("PATCH", f"/auth/users/{users['owner']}/status", {"status": "LOCKED"}),
        ("POST", f"/courses/{cid}/status", {"status": "DRAFT"}),
        ("DELETE", f"/exams/{eid}", None),
        ("POST", f"/exams/{eid}/publish", None),
        ("POST", "/exports", {"request_id": str(uuid4()), "kind": "GRADEBOOK", "course_id": cid}),
    ]
    async with engine.connect() as conn:
        audit_count = await conn.scalar(text("SELECT COUNT(*) FROM audit_logs"))
    headers = authorization(tokens[actor]["access_token"]) if actor else {}
    for method, path, body in requests:
        response = await client.request(method, "/api/v1" + path, headers=headers, json=body)
        assert response.status_code == (401 if actor is None else 403), (
            method,
            path,
            response.text,
        )
        assert_error(response, 401 if actor is None else 403)
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT COUNT(*) FROM audit_logs")) == audit_count
        assert await conn.scalar(text("SELECT COUNT(*) FROM export_jobs")) == 0
        assert (
            await conn.scalar(text("SELECT status FROM exams WHERE id=:id"), {"id": eid}) == "DRAFT"
        )
        assert (
            await conn.scalar(text("SELECT status FROM courses WHERE id=:id"), {"id": cid})
            == "PUBLISHED"
        )
    assert (await call("GET", "/auth/me", actor="student"))["roles"] == ["STUDENT"]


async def test_peer_student_cannot_read_write_attempt_submission_grade_or_notifications(api):
    call, engine, cid, _, question, eid, _ = await setup_exam(api)
    peer, peer_headers = await peer_student(api, cid)
    _, _, _, tokens, client = api
    await call("POST", f"/exams/{eid}/publish")
    attempt = await call("POST", f"/exams/{eid}/attempts", actor="student", expected=201)
    attempt_path = f"/attempts/{attempt['id']}"
    for method, path, body in [
        ("GET", attempt_path, None),
        ("POST", attempt_path + "/submit", None),
        (
            "PUT",
            attempt_path + f"/answers/{question['id']}",
            {"selected_option_ids": [question["options"][0]["id"]], "expected_version": 0},
        ),
        (
            "POST",
            attempt_path + "/events",
            {"client_event_id": str(uuid4()), "event_type": "TAB_HIDDEN"},
        ),
    ]:
        response = await client.request(method, "/api/v1" + path, headers=peer_headers, json=body)
        assert_error(response, 404)
    own = await call("GET", attempt_path, actor="student")
    assert own["status"] == "IN_PROGRESS" and own["server_version"] == 0 and own["answers"] == []
    assert "is_correct" not in str(own) and "question_snapshot" not in own

    assignment = await call(
        "POST", f"/courses/{cid}/assignments", expected=201, json=assignment_body()
    )
    base = f"/courses/{cid}/assignments/{assignment['id']}"
    await call("POST", base + "/status", json={"status": "PUBLISHED"})
    submission = await call(
        "POST",
        base + "/submissions/file",
        actor="student",
        expected=201,
        content=b"%PDF-1.7\nprivate answer",
        headers={"Content-Type": "application/pdf", "X-File-Name": "answer.pdf"},
    )
    files_path = base + f"/submissions/{submission['id']}/files"
    files = await call("GET", files_path, actor="student")
    await peer("GET", files_path, expected=404)
    assert_error(
        await client.get(
            "/api/v1" + files_path + f"/{files[0]['id']}/content",
            headers=peer_headers,
        ),
        404,
    )
    assert await peer("GET", base + "/submissions/mine") == []
    own_submission = await peer(
        "POST", base + "/submissions", expected=201, json={"answer_text": "Peer"}
    )
    swapped = base + f"/submissions/{own_submission['id']}/files/{files[0]['id']}/content"
    assert_error(await client.get("/api/v1" + swapped, headers=peer_headers), 404)

    await call("POST", attempt_path + "/submit", actor="student")
    grade = (await call("GET", f"/courses/{cid}/grades"))[0]
    assert await peer("GET", f"/courses/{cid}/grades/me") == []
    await peer("GET", f"/grades/{grade['id']}", expected=403)
    await call("POST", f"/grades/{grade['id']}/publish", json={"expected_version": 1})
    assert len(await call("GET", f"/courses/{cid}/grades/me", actor="student")) == 1
    assert await peer("GET", f"/courses/{cid}/grades/me") == []
    notices = await call("GET", "/notifications", actor="student")
    notice = next(n for n in notices["items"] if n["type"] == "GRADE_PUBLISHED")
    await peer("PATCH", f"/notifications/{notice['id']}/read")
    async with engine.connect() as conn:
        assert not await conn.scalar(
            text("SELECT is_read FROM notifications WHERE id=:id"), {"id": notice["id"]}
        )
        assert await conn.scalar(text("SELECT COUNT(*) FROM attempt_events")) == 0
    response = await client.get(
        "/api/v1" + files_path + f"/{files[0]['id']}/content",
        headers=authorization(tokens["student"]["access_token"]),
    )
    assert response.status_code == 200 and response.content == b"%PDF-1.7\nprivate answer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    enrollment = f"/courses/{cid}/enrollments/{api[2]['student']}"
    await call("PATCH", enrollment, json={"status": "SUSPENDED"})
    await call("GET", files_path, actor="student", expected=403)
    await call("GET", files_path + f"/{files[0]['id']}/content", actor="student", expected=403)
    await call("PATCH", enrollment, json={"status": "ACTIVE"})
    outside = client._transport.app.state.settings.private_storage_root.parent / "outside.txt"
    outside.write_text("private-outside-storage", encoding="utf-8")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE submission_files SET location=:location WHERE id=:id"),
            {"location": str(outside), "id": files[0]["id"]},
        )
    await call("GET", files_path + f"/{files[0]['id']}/content", actor="student", expected=404)
    await call(
        "PATCH", f"/auth/users/{api[2]['student']}/status", actor="admin", json={"status": "LOCKED"}
    )
    await call("GET", files_path, actor="student", expected=401)


async def test_lesson_file_parent_scope_revocation_path_containment_and_upload_cleanup(
    api, tmp_path
):
    call, engine, users, tokens, client = api
    cid = (await new_course(call))["id"]
    mid, lid = await new_content(call, cid)
    other_cid = (await new_course(call, code="SECOND"))["id"]
    other_mid, other_lid = await new_content(call, other_cid)
    base = f"/courses/{cid}/modules/{mid}/lessons/{lid}/resources"
    settings = client._transport.app.state.settings
    root = settings.private_storage_root
    for content, mime, expected in [
        (b"MZ-fake", "application/pdf", 422),
        (b"<script>secret</script>", "text/html", 422),
        (b"", "application/pdf", 422),
        (b"x" * 1025, "application/pdf", 413),
    ]:
        await call(
            "POST",
            base + "/file",
            expected=expected,
            content=content,
            headers={"Content-Type": mime, "X-File-Name": "bad.pdf"},
        )
    assert not list(root.rglob("*.*"))
    uploaded = await call(
        "POST",
        base + "/file",
        expected=201,
        content=b"%PDF-1.7\nprivate lesson",
        headers={"Content-Type": "application/pdf", "X-File-Name": "../../secret.pdf"},
    )
    assert uploaded["title"] == "secret.pdf" and "location" not in uploaded
    path = base + f"/{uploaded['id']}/content"
    foreign_base = f"/courses/{other_cid}/modules/{other_mid}/lessons/{other_lid}/resources"
    await call("GET", foreign_base + f"/{uploaded['id']}/content", expected=404)
    await call("GET", f"/courses/{other_cid}/modules/{mid}/lessons/{lid}/resources", expected=404)
    await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
    await call(
        "POST", f"/courses/{cid}/enrollments", expected=201, json={"student_id": users["student"]}
    )
    enrollment = f"/courses/{cid}/enrollments/{users['student']}"
    await call("PATCH", enrollment, json={"status": "ACTIVE"})
    headers = authorization(tokens["student"]["access_token"])
    response = await client.get("/api/v1" + path, headers=headers)
    assert response.status_code == 200 and response.content == b"%PDF-1.7\nprivate lesson"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    for status in ("SUSPENDED", "ACTIVE"):
        await call("PATCH", enrollment, json={"status": status})
        response = await client.get("/api/v1" + path, headers=headers)
        assert response.status_code == (403 if status == "SUSPENDED" else 200)
    await call("POST", f"/courses/{cid}/status", json={"status": "DRAFT"})
    await call("GET", path, actor="student", expected=403)
    for location in ("../../outside.txt", str(tmp_path / "outside.txt")):
        (tmp_path / "outside.txt").write_text("outside-storage-secret", encoding="utf-8")
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE lesson_resources SET location=:location WHERE id=:id"),
                {"location": location, "id": uploaded["id"]},
            )
        await call("GET", path, expected=404)
    assert (tmp_path / "outside.txt").read_text(encoding="utf-8") == "outside-storage-secret"


async def test_export_owner_isolation_live_permission_and_staff_revocation(api):
    call, engine, cid, _, _, _, _ = await setup_exam(api)
    _, _, users, tokens, client = api
    job = await call(
        "POST",
        "/exports",
        expected=202,
        json={
            "request_id": str(uuid4()),
            "kind": "LEARNERS",
            "course_id": cid,
        },
    )
    assert await process_exports(engine, client._transport.app.state.settings) == 1
    path = f"/exports/{job['id']}"
    for actor in (None, "student", "other", "admin"):
        for suffix in ("", "/content"):
            expected = 401 if actor is None else 403 if actor == "student" else 404
            await call("GET", path + suffix, actor=actor, expected=expected)
        if actor in ("other", "admin"):
            assert (await call("GET", "/exports", actor=actor))["items"] == []
    await call("DELETE", "/roles/INSTRUCTOR/permissions/course.read", actor="admin")
    await call("GET", path + "/content", expected=403)
    await call("PUT", "/roles/INSTRUCTOR/permissions/course.read", actor="admin")
    response = await client.get(
        "/api/v1" + path + "/content", headers=authorization(tokens["owner"]["access_token"])
    )
    assert response.status_code == 200
    await call(
        "PUT", f"/courses/{cid}/staff/{users['other']}", actor="admin", json={"role": "INSTRUCTOR"}
    )
    staff_job = await call(
        "POST",
        "/exports",
        actor="other",
        expected=202,
        json={
            "request_id": str(uuid4()),
            "kind": "LEARNERS",
            "course_id": cid,
        },
    )
    assert await process_exports(engine, client._transport.app.state.settings) == 1
    staff_path = f"/exports/{staff_job['id']}"
    assert (await call("GET", staff_path, actor="other"))["status"] == "READY"
    await call("DELETE", f"/courses/{cid}/staff/{users['other']}", actor="admin")
    await call("GET", staff_path, actor="other", expected=403)
    await call("GET", staff_path + "/content", actor="other", expected=403)
    async with engine.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT COUNT(*) FROM audit_logs WHERE action='export.download'")
            )
            == 1
        )
