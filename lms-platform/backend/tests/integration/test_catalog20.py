"""Real MySQL proof that the catalog supports grading and safe seed reruns."""

import json

import pytest
from sqlalchemy import text

from scripts.seed_catalog20 import CATALOG_PASSWORD, record_demo_logins, seed_catalog
from scripts.verify_catalog20 import verify_catalog
from tests.integration.test_week2_mysql import api as api

pytestmark = pytest.mark.integration


async def test_catalog_coverage_attempt_grading_files_and_rerun_preserve_activity(api):
    _, engine, users, _, client = api
    settings = client._transport.app.state.settings
    created_files = []
    async with engine.begin() as connection:
        seeded = await seed_catalog(
            connection, settings, instructor_id=users["owner"], created_files=created_files
        )
    assert seeded["courses_seeded"] == 20 and len(created_files) == 40
    await record_demo_logins(engine, settings, CATALOG_PASSWORD)
    report = await verify_catalog(engine, settings)
    assert report["questions"] == 60 and len(report["courses"]) == 20
    assert all(t["rows"] >= 20 for t in report["tables"].values() if t["minimum"] == 20)
    assert report["private_submission_files_verified"] == report["export_files_verified"] == 20

    async with engine.connect() as connection:
        course_id = await connection.scalar(
            text("SELECT id FROM courses WHERE code='CATALOG20_01'")
        )
        exam_id = await connection.scalar(
            text("SELECT id FROM exams WHERE course_id=:course"), {"course": course_id}
        )
        attempt_id = await connection.scalar(
            text("SELECT id FROM exam_attempts WHERE exam_id=:exam"), {"exam": exam_id}
        )
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "login": "catalog_student_01",
            "password": CATALOG_PASSWORD,
        },
    )
    assert login.status_code == 200
    auth = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
    history = await client.get(f"/api/v1/attempts/{attempt_id}", headers=auth)
    assert history.status_code == 200
    assert len(history.json()["data"]["questions"]) == 3
    assert "is_correct" not in history.text and "explanation" not in history.text
    started = await client.post(f"/api/v1/exams/{exam_id}/attempts", headers=auth)
    assert started.status_code == 201
    second = started.json()["data"]
    version = second["server_version"]
    async with engine.connect() as connection:
        snapshot = json.loads(
            await connection.scalar(
                text("SELECT question_snapshot FROM exam_attempts WHERE id=:id"),
                {"id": second["id"]},
            )
        )
    for question in snapshot:
        option = next(o["id"] for o in question["options"] if o["is_correct"])
        saved = await client.put(
            f"/api/v1/attempts/{second['id']}/answers/{question['id']}",
            headers=auth,
            json={"selected_option_ids": [option], "expected_version": version},
        )
        assert saved.status_code == 200
        version = saved.json()["data"]["server_version"]
    submitted = await client.post(f"/api/v1/attempts/{second['id']}/submit", headers=auth)
    assert submitted.status_code == 200
    async with engine.connect() as connection:
        result = (
            await connection.execute(
                text("SELECT score,max_score,status FROM exam_attempts WHERE id=:id"),
                {"id": second["id"]},
            )
        ).one()
        assert result.score == result.max_score == 30 and result.status == "SUBMITTED"
        before = await connection.scalar(text("SELECT COUNT(*) FROM audit_logs"))
    async with engine.begin() as connection:
        repeated = await seed_catalog(
            connection, settings, instructor_id=users["owner"], created_files=created_files
        )
    assert repeated["courses_seeded"] == 0 and repeated["courses_preserved"] == 20
    assert len(created_files) == 40
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT COUNT(*) FROM audit_logs")) == before
        assert (
            await connection.scalar(
                text("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=:exam"), {"exam": exam_id}
            )
            == 2
        )
