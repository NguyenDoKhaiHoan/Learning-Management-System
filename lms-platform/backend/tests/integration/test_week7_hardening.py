"""Week 7 hardening scenarios on a disposable real MySQL database."""

import pytest
from sqlalchemy import text

from src.config.config import Settings
from src.jobs.processors.notifications import process_notification_emails
from src.modules.notification.infrastructure.email import MemoryEmailAdapter
from src.modules.notification.infrastructure.repository import NotificationRepository
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_content, new_course

pytestmark = pytest.mark.integration


async def activate_student(call, course_id, student_id):
    await call(
        "POST",
        f"/courses/{course_id}/enrollments",
        actor="owner",
        json={"student_id": student_id},
        expected=201,
    )
    await call(
        "PATCH",
        f"/courses/{course_id}/enrollments/{student_id}",
        actor="owner",
        json={"status": "ACTIVE"},
    )


async def test_notification_preferences_outbox_and_worker(api):
    call, engine, users, _, _ = api
    await call(
        "PUT",
        "/notifications/preferences",
        actor="student",
        json={"email_enabled": True, "event_types": ["WEEK7_TEST"]},
    )
    async with engine.begin() as connection:
        notification_id = await NotificationRepository(connection).create(
            recipient_id=users["student"],
            type="WEEK7_TEST",
            title="Test notification",
            body="Durable email body",
        )
    adapter = MemoryEmailAdapter()
    settings = Settings(
        _env_file=None,
        database_url="mysql+aiomysql://unused:unused@localhost/lms",
        jwt_secret="week7-notification-secret-" + "x" * 20,
        email_delivery_enabled=True,
        email_max_attempts=2,
    )
    assert await process_notification_emails(engine, settings, adapter=adapter) == 1
    assert len(adapter.messages) == 1
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text("SELECT status FROM notification_deliveries WHERE notification_id=:id"),
                {"id": notification_id},
            )
        ).one()
    assert row.status == "SENT"


async def test_forum_moderation_membership_review_and_metrics(api):
    call, engine, users, _, client = api
    course_id = (await new_course(call, code="MODERATION"))["id"]
    await new_content(call, course_id)
    await call("POST", f"/courses/{course_id}/status", json={"status": "PUBLISHED"})
    await activate_student(call, course_id, users["student"])
    thread = await call(
        "POST",
        f"/courses/{course_id}/forum/threads",
        actor="student",
        expected=201,
        json={"title": "Needs review", "body": "A post"},
    )
    await call(
        "POST",
        f"/courses/{course_id}/forum/threads/{thread['id']}/moderate",
        actor="owner",
        json={"action": "LOCKED", "reason": "Review pending"},
    )
    await call(
        "POST",
        f"/courses/{course_id}/forum/threads/{thread['id']}/messages",
        actor="student",
        expected=409,
        json={"body": "blocked"},
    )
    await call(
        "POST",
        f"/courses/{course_id}/forum/threads/{thread['id']}/moderate",
        actor="owner",
        json={"action": "OPEN"},
    )
    reply = await call(
        "POST",
        f"/courses/{course_id}/forum/threads/{thread['id']}/messages",
        actor="student",
        expected=201,
        json={"body": "visible"},
    )
    await call(
        "POST",
        f"/courses/{course_id}/forum/threads/{thread['id']}/messages/{reply['id']}/moderate",
        actor="owner",
        json={"action": "HIDE", "reason": "Needs review"},
    )
    detail = await call(
        "GET", f"/courses/{course_id}/forum/threads/{thread['id']}", actor="student"
    )
    assert detail["messages"] == []
    requested = await call(
        "POST",
        f"/courses/{course_id}/forum/membership-requests",
        actor="student",
        expected=201,
        json={"reason": "I need to join the discussion"},
    )
    listed = await call(
        "GET", f"/courses/{course_id}/forum/membership-requests", actor="owner"
    )
    assert listed[0]["id"] == requested["id"]
    reviewed = await call(
        "PATCH",
        f"/courses/{course_id}/forum/membership-requests/{users['student']}",
        actor="owner",
        json={"status": "APPROVED"},
    )
    assert reviewed["status"] == "APPROVED"
    queue = await call("GET", f"/courses/{course_id}/forum/moderation/queue", actor="owner")
    assert queue["items"] == []
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200 and "lms_http_requests_total" in metrics.text
