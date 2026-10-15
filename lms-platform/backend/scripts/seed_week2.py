"""Idempotent demo fixtures, strictly restricted to demo/test databases."""

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta

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
DEMO_ASSIGNMENT_TITLE = "Bài thực hành LMS"
DEMO_EXAM_TITLE = "Kiểm tra tổng kết LMS"


async def _ensure_demo_assessments(connection, *, course_id: int, instructor_id: int):
    """Create the stable assignment/exam fixtures without touching learner state."""
    repo = CourseRepository(connection)
    assignment = await repo.fetch_one(
        """SELECT id,course_id,created_by,status FROM assignments
           WHERE course_id=:course AND title=:title AND deleted_at IS NULL FOR UPDATE""",
        {"course": course_id, "title": DEMO_ASSIGNMENT_TITLE},
    )
    if assignment:
        if assignment["created_by"] != instructor_id or assignment["status"] not in {
            "PUBLISHED",
            "CLOSED",
        }:
            raise ValueError("Existing demo assignment differs; no assignment was overwritten")
        assignment_id = assignment["id"]
    else:
        now = datetime.now(UTC).replace(tzinfo=None)
        assignment_id = await repo.insert(
            """INSERT INTO assignments
               (course_id,title,description,status,opens_at,due_at,allow_late,late_until,
                max_attempts,max_file_bytes,allowed_mime_types,max_score,created_by)
               VALUES (:course,:title,:description,'PUBLISHED',:opens,:due,1,:late,
                       3,10485760,'application/pdf',100,:user)""",
            {
                "course": course_id,
                "title": DEMO_ASSIGNMENT_TITLE,
                "description": "Nộp câu trả lời hoặc tệp PDF cho khóa học mẫu.",
                "opens": now - timedelta(days=1),
                "due": now + timedelta(days=30),
                "late": now + timedelta(days=37),
                "user": instructor_id,
            },
        )

    bank = await repo.fetch_one(
        """SELECT id,course_id,created_by,status FROM question_banks
           WHERE course_id=:course AND name='DEMO_WEEK2_BANK' FOR UPDATE""",
        {"course": course_id},
    )
    if bank:
        if bank["created_by"] != instructor_id or bank["course_id"] != course_id:
            raise ValueError("Existing demo question bank differs; no bank was overwritten")
        bank_id = bank["id"]
    else:
        bank_id = await repo.insert(
            """INSERT INTO question_banks(course_id,name,description,status,created_by)
               VALUES (:course,'DEMO_WEEK2_BANK','Câu hỏi cho khóa học mẫu','PUBLISHED',:user)""",
            {"course": course_id, "user": instructor_id},
        )
    question = await repo.fetch_one(
        """SELECT id,bank_id,status FROM questions
           WHERE bank_id=:bank AND prompt='Progress trong LMS được cập nhật ở đâu?' FOR UPDATE""",
        {"bank": bank_id},
    )
    if question:
        if question["status"] != "PUBLISHED":
            raise ValueError("Existing demo question differs; no question was overwritten")
        question_id = question["id"]
    else:
        question_id = await repo.insert(
            """INSERT INTO questions
               (bank_id,question_type,prompt,explanation,points,status)
               VALUES (:bank,'SINGLE','Progress trong LMS được cập nhật ở đâu?',
                       'Tiến độ được lưu qua API progress của khóa học.',10,'PUBLISHED')""",
            {"bank": bank_id},
        )
        await repo.insert(
            """INSERT INTO question_options
               (question_id,option_key,option_text,is_correct)
               VALUES (:question,'A','Trong API progress',1)""",
            {"question": question_id},
        )
        await repo.insert(
            """INSERT INTO question_options
               (question_id,option_key,option_text,is_correct)
               VALUES (:question,'B','Chỉ trong trình duyệt',0)""",
            {"question": question_id},
        )

    exam = await repo.fetch_one(
        """SELECT id,course_id,created_by,status FROM exams
           WHERE course_id=:course AND title=:title FOR UPDATE""",
        {"course": course_id, "title": DEMO_EXAM_TITLE},
    )
    if exam:
        if exam["created_by"] != instructor_id or exam["status"] not in {"PUBLISHED", "CLOSED"}:
            raise ValueError("Existing demo exam differs; no exam was overwritten")
        exam_id = exam["id"]
    else:
        now = datetime.now(UTC).replace(tzinfo=None)
        exam_id = await repo.insert(
            """INSERT INTO exams
               (course_id,title,instructions,status,opens_at,due_at,duration_seconds,
                max_attempts,shuffle_questions,show_results,pass_score,created_by)
               VALUES (:course,:title,:instructions,'PUBLISHED',:opens,:due,1800,
                       2,0,1,5,:user)""",
            {
                "course": course_id,
                "title": DEMO_EXAM_TITLE,
                "instructions": "Chọn đáp án đúng. Bạn có 30 phút và tối đa 2 lần làm.",
                "opens": now - timedelta(days=1),
                "due": now + timedelta(days=30),
                "user": instructor_id,
            },
        )
    exam_question = await repo.fetch_one(
        "SELECT id FROM exam_questions WHERE exam_id=:exam AND question_id=:question",
        {"exam": exam_id, "question": question_id},
    )
    if not exam_question:
        await repo.insert(
            """INSERT INTO exam_questions(exam_id,question_id,position,points)
               VALUES (:exam,:question,1,10)""",
            {"exam": exam_id, "question": question_id},
        )
    return {"assignment_id": str(assignment_id), "exam_id": str(exam_id)}


async def seed_demo(connection, password: str = DEMO_PASSWORD, *, allow_lms: bool = False):
    """Caller owns the transaction. Existing demo learning progress is preserved."""
    database = connection.engine.url.database or ""
    if not (database == "lms" and allow_lms) and not database.startswith(
        ("lms_demo_", "lms_test_")
    ):
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
    assessments = await _ensure_demo_assessments(
        connection, course_id=course_id, instructor_id=users["instructor"]
    )
    return {
        "users": {name: str(uid) for name, uid in users.items()},
        "course_id": str(course_id),
        **assessments,
    }


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
