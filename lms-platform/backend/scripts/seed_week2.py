"""Idempotent demo fixtures, strictly restricted to demo/test databases."""

import asyncio
import json
import os

from src.config.config import Settings
from src.core.database.database import build_engine
from src.modules.course.infrastructure.repository import CourseRepository
from src.modules.enrollment.infrastructure.repository import EnrollmentRepository
from src.modules.identity_access.application.passwords import hash_password, verify_password
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.learning_content.infrastructure.repository import ContentRepository
from src.modules.user_role.infrastructure.repository import RoleRepository

DEMO_PASSWORD = "LmsDemo-Week2!2026"
DEMO_USERS = {"admin": "ADMIN", "instructor": "INSTRUCTOR", "student": "STUDENT"}


async def seed_demo(connection, password: str = DEMO_PASSWORD):
    """Caller owns the transaction. Existing demo learning progress is preserved."""
    database = connection.engine.url.database or ""
    if not database.startswith(("lms_demo_", "lms_test_")):
        raise ValueError("Demo seed requires a database named lms_demo_* or lms_test_*")
    if not 8 <= len(password) <= 128:
        raise ValueError("Demo password must have 8..128 characters")
    roles = RoleRepository(connection)
    identity = IdentityRepository(connection)
    users = {}
    for name, code in DEMO_USERS.items():
        await roles.execute(
            "INSERT INTO roles (code,name) VALUES (:code,:code) ON DUPLICATE KEY UPDATE code=code",
            {"code": code},
        )
        role = await roles.get_role(code)
        username = "demo_" + name
        email = username + "@example.test"
        existing = await identity.fetch_one(
            """SELECT id,email,username,status,deleted_at,hashed_password FROM users
               WHERE username=:username OR email=:email FOR UPDATE""",
            {"username": username, "email": email},
        )
        if existing:
            if (
                existing["email"] != email
                or existing["username"] != username
                or existing["deleted_at"] is not None
                or existing["status"] != "ACTIVE"
                or not verify_password(password, existing["hashed_password"])
            ):
                raise ValueError("Existing demo account differs; no account was overwritten")
            user_id = existing["id"]
        else:
            user_id = await identity.create_user(
                email=email,
                username=username,
                hashed_password=hash_password(password),
                status="ACTIVE",
            )
        users[name] = user_id
        await roles.execute(
            """INSERT INTO user_roles (user_id,role_id) VALUES (:user,:role)
               ON DUPLICATE KEY UPDATE user_id=user_id""",
            {"user": user_id, "role": role["id"]},
        )
        for permission in ("course.read", "course.write", "course.publish"):
            if code == "STUDENT" and permission != "course.read":
                continue
            await roles.execute(
                "INSERT INTO permissions (code) VALUES (:code) ON DUPLICATE KEY UPDATE code=code",
                {"code": permission},
            )
            await roles.execute(
                """INSERT INTO role_permissions (role_id,permission_id)
                   SELECT :role,id FROM permissions WHERE code=:code
                   ON DUPLICATE KEY UPDATE role_id=role_id""",
                {"role": role["id"], "code": permission},
            )
    courses = CourseRepository(connection)
    course = await courses.fetch_one(
        "SELECT id,created_by,deleted_at FROM courses WHERE code='DEMO_WEEK2' FOR UPDATE"
    )
    if course:
        if course["created_by"] != users["instructor"] or course["deleted_at"] is not None:
            raise ValueError("Existing demo course differs; no course was overwritten")
        course_id = course["id"]
    else:
        course_id = await courses.create(
            code="DEMO_WEEK2",
            title="Nhập môn học tập trực tuyến",
            description="Khóa học mẫu để khám phá nội dung và quy trình ghi danh.",
            created_by=users["instructor"],
        )
        content = ContentRepository(connection)
        module_id = await content.create_module(course_id=course_id, title="Bắt đầu", position=1)
        await content.create_lesson(
            module_id=module_id,
            title="Chào mừng bạn đến với LMS",
            position=1,
            lesson_type="ARTICLE",
            content="Đọc bài học, trao đổi với giảng viên và học theo nhịp của bạn.",
        )
        await courses.change_status(course_id, expected="DRAFT", new="PUBLISHED")
    enrollment = EnrollmentRepository(connection)
    await enrollment.execute(
        """INSERT INTO course_staff (course_id,user_id,role) VALUES (:course,:user,'INSTRUCTOR')
           ON DUPLICATE KEY UPDATE user_id=user_id""",
        {"course": course_id, "user": users["instructor"]},
    )
    if not await enrollment.get(student_id=users["student"], course_id=course_id):
        eid = await enrollment.create(student_id=users["student"], course_id=course_id)
        await enrollment.change_status(eid, expected="PENDING", new="ACTIVE")
    return {"users": {name: str(uid) for name, uid in users.items()}, "course_id": str(course_id)}


async def main():
    settings = Settings()
    if settings.app_env not in {"development", "test"}:
        raise ValueError("Demo seed is only available in development/test")
    engine = build_engine(settings)
    try:
        async with engine.begin() as connection:
            result = await seed_demo(connection, os.getenv("LMS_DEMO_PASSWORD", DEMO_PASSWORD))
        print(json.dumps(result))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
