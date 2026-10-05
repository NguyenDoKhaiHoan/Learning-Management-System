"""Create a repeatable exam/grading checkpoint in the application's lms database."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from scripts.seed_week2 import DEMO_PASSWORD, seed_demo
from src.config.config import Settings
from src.core.database.database import build_engine
from src.main import create_app


async def main():
    settings = Settings()
    if settings.sqlalchemy_url.database != "lms" or settings.app_env != "development":
        raise ValueError("This checkpoint requires development database lms")
    engine = build_engine(settings)
    try:
        async with engine.begin() as conn:
            fixtures = await seed_demo(conn, allow_lms=True)
            existing = await conn.scalar(text("SELECT id FROM courses WHERE code='DEMO_WEEK4'"))
        app = create_app(settings)
        app.state.db_engine = engine
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://demo") as client:
            tokens = {}
            for actor in ("instructor", "student"):
                response = await client.post(
                    "/api/v1/auth/login", json={"login": "demo_" + actor, "password": DEMO_PASSWORD}
                )
                response.raise_for_status()
                tokens[actor] = response.json()["data"]["access_token"]

            async def call(method, path, actor="instructor", body=None):
                response = await client.request(
                    method,
                    "/api/v1" + path,
                    json=body,
                    headers={"Authorization": "Bearer " + tokens[actor]},
                )
                response.raise_for_status()
                return response.json()["data"]

            if existing:
                grades = await call("GET", f"/courses/{existing}/grades/me", "student")
                progress = await call("GET", f"/courses/{existing}/progress/me", "student")
                assert grades and progress["completed_at"]
                print(
                    json.dumps(
                        {
                            "database": "lms",
                            "course_id": str(existing),
                            "checkpoint": "already verified",
                        }
                    )
                )
                return
            cid = (
                await call(
                    "POST",
                    "/courses",
                    body={
                        "code": "DEMO_WEEK4",
                        "title": "Kiểm tra và công bố kết quả",
                        "description": "Demo tuần 4",
                    },
                )
            )["id"]
            mid = (await call("POST", f"/courses/{cid}/modules", body={"title": "Ôn tập"}))["id"]
            lid = (
                await call(
                    "POST",
                    f"/courses/{cid}/modules/{mid}/lessons",
                    body={
                        "title": "Quy trình kiểm tra",
                        "lesson_type": "ARTICLE",
                        "content": "Học bài, làm bài thi, nhận kết quả đã công bố.",
                    },
                )
            )["id"]
            await call(
                "PUT",
                f"/courses/{cid}/completion-rule",
                body={
                    "required_lesson_percent": 100,
                    "require_published_exam_grades": True,
                    "minimum_grade_percent": 80,
                },
            )
            bid = (await call("POST", f"/courses/{cid}/question-banks", body={"name": "Ôn tập"}))[
                "id"
            ]
            question = await call(
                "POST",
                f"/question-banks/{bid}/questions",
                body={
                    "question_type": "SINGLE",
                    "prompt": "Điểm nào học viên được xem?",
                    "options": [
                        {"key": "A", "text": "Điểm đã công bố", "is_correct": True},
                        {"key": "B", "text": "Mọi điểm nháp"},
                    ],
                },
            )
            now = datetime.now(UTC)
            eid = (
                await call(
                    "POST",
                    f"/courses/{cid}/exams",
                    body={
                        "title": "Kiểm tra ôn tập",
                        "opens_at": (now - timedelta(minutes=1)).isoformat(),
                        "due_at": (now + timedelta(days=365)).isoformat(),
                        "duration_seconds": 600,
                        "max_attempts": 2,
                        "allow_resume": True,
                        "questions": [{"question_id": question["id"], "position": 1, "points": 10}],
                    },
                )
            )["id"]
            await call("POST", f"/courses/{cid}/status", body={"status": "PUBLISHED"})
            await call(
                "POST",
                f"/courses/{cid}/enrollments",
                body={"student_id": fixtures["users"]["student"]},
            )
            await call(
                "PATCH",
                f"/courses/{cid}/enrollments/{fixtures['users']['student']}",
                body={"status": "ACTIVE"},
            )
            await call("POST", f"/exams/{eid}/publish")
            await call(
                "PUT", f"/courses/{cid}/lessons/{lid}/progress", "student", {"status": "COMPLETED"}
            )
            attempt = await call("POST", f"/exams/{eid}/attempts", "student")
            await call(
                "PUT",
                f"/attempts/{attempt['id']}/answers/{question['id']}",
                "student",
                {"selected_option_ids": [question["options"][0]["id"]], "expected_version": 0},
            )
            await call("POST", f"/attempts/{attempt['id']}/submit", "student")
            assert await call("GET", f"/courses/{cid}/grades/me", "student") == []
            grade = (await call("GET", f"/courses/{cid}/grades"))[0]
            await call("POST", f"/grades/{grade['id']}/publish", body={"expected_version": 1})
            grades = await call("GET", f"/courses/{cid}/grades/me", "student")
            progress = await call("GET", f"/courses/{cid}/progress/me", "student")
            assert float(grades[0]["score"]) == 10 and progress["completed_at"]
            print(
                json.dumps(
                    {
                        "database": "lms",
                        "course_id": cid,
                        "exam_id": eid,
                        "grade_id": grade["id"],
                        "score": 10,
                        "completed": True,
                    }
                )
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
