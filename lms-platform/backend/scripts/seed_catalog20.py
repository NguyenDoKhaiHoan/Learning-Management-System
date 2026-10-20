"""Twenty linked, source-backed course fixtures for development/test only.

Run with --apply --allow-lms to seed local lms; default mode only verifies.
Existing catalog20 v2 courses are never changed by reruns. Operational rows and
accounts are explicitly simulated; no real learner identities or official exams.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from httpx import ASGITransport, AsyncClient

from scripts.catalog20_content import COURSES, validate_content
from src.config.config import Settings
from src.core.database.database import build_engine
from src.core.database.sql import SqlRepository
from src.main import create_app
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.file_management.domain.policy import validate_file_content
from src.modules.file_management.infrastructure.scanner import scan_file
from src.modules.gradebook.infrastructure.repository import GradeRepository
from src.modules.identity_access.application.passwords import hash_password
from src.modules.reporting_export.application.reports import LEARNER_COLUMNS
from src.modules.reporting_export.domain.csv import csv_bytes

CATALOG_PASSWORD = "Catalog20-Demo!2026"
REFERENCE_TABLES = {
    "alembic_version": "Migration head; exactly one current revision.",
    "cache_versions": "Singleton invalidation counter; CHECK(id=1).",
    "roles": "Application supports ADMIN, INSTRUCTOR, STUDENT.",
    "permissions": "Application supports course.read/write/publish.",
    "role_permissions": "Only meaningful grants for the supported role/permission catalog.",
}
TRACE = "catalog20-v2"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, default=str)


async def upsert_fixture(repo, table, match, values):
    """Identifiers are developer-owned constants; all data is bound separately.

    Only called for rows belonging to a course being created/refined by this seed.
    Subsequent v2 runs skip the entire course and leave its learning history alone.
    """
    where = " AND ".join(f"{key}=:_key_{key}" for key in match)
    params = {f"_key_{key}": value for key, value in match.items()}
    existing = await repo.fetch_one(f"SELECT id FROM {table} WHERE {where} FOR UPDATE", params)
    if existing:
        if values:
            await repo.execute(
                f"UPDATE {table} SET "
                + ",".join(f"{key}=:{key}" for key in values)
                + " WHERE id=:_fixture_id",
                values | {"_fixture_id": existing["id"]},
            )
        return int(existing["id"])
    data = match | values
    return await repo.insert(
        f"INSERT INTO {table} ("
        + ",".join(data)
        + ") VALUES ("
        + ",".join(f":{key}" for key in data)
        + ")",
        data,
    )


async def fixture_users(repo, password):
    role = await repo.fetch_one("SELECT id FROM roles WHERE code='STUDENT'")
    if role is None:
        raise ValueError("Bootstrap the supported roles before running this seed")
    password_hash = hash_password(password)
    users = []
    for index in range(1, 21):
        username = f"catalog_student_{index:02d}"
        email = f"catalog.student.{index:02d}@example.test"
        existing = await repo.fetch_one(
            """SELECT id,username,email,status,deleted_at FROM users
               WHERE username=:username OR email=:email FOR UPDATE""",
            {"username": username, "email": email},
        )
        if existing:
            if (existing["username"], existing["email"]) != (username, email):
                raise ValueError("Catalog account conflicts with an existing identity")
            if existing["deleted_at"] or existing["status"] != "ACTIVE":
                raise ValueError("Existing catalog account has changed; left unchanged")
            user_id = existing["id"]
        else:
            user_id = await repo.insert(
                """INSERT INTO users(email,username,hashed_password,status)
                   VALUES (:email,:username,:password,'ACTIVE')""",
                {"email": email, "username": username, "password": password_hash},
            )
            await upsert_fixture(
                repo, "user_roles", {"user_id": user_id, "role_id": role["id"]}, {}
            )
        users.append(int(user_id))
        await repo.execute(
            """INSERT IGNORE INTO notification_preferences(user_id,email_enabled,event_types)
               VALUES (:user,0,'[]')""",
            {"user": user_id},
        )
    return users


async def create_private_file(settings, relative, content, created_files):
    root = settings.private_storage_root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Fixture file outside private storage")
    digest = hashlib.sha256(content).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Existing fixture file was modified; left unchanged")
    else:
        with path.open("xb") as stream:
            stream.write(content)
        created_files.append(path)
    return digest, path


async def seed_catalog(
    connection,
    settings,
    *,
    instructor_id,
    created_files,
    password=CATALOG_PASSWORD,
    refine_initial=False,
):
    validate_content()
    if settings.app_env not in {"development", "test"}:
        raise ValueError("Catalog data is restricted to development/test")
    repo = SqlRepository(connection)
    students = await fixture_users(repo, password)
    now = datetime.now(UTC).replace(tzinfo=None)
    opens, due = now - timedelta(days=7), now + timedelta(days=180)
    started = now - timedelta(days=2)
    submitted = started + timedelta(minutes=10)
    seeded = 0
    for index, course in enumerate(COURSES, 1):
        code, trace = f"CATALOG20_{index:02d}", f"{TRACE}-{index:02d}"
        if await repo.fetch_one(
            "SELECT id FROM audit_logs WHERE action='catalog20.seed' AND trace_id=:trace",
            {"trace": trace},
        ):
            continue
        old = await repo.fetch_one("SELECT id FROM courses WHERE code=:code", {"code": code})
        if old and not refine_initial:
            raise ValueError("Initial catalog fixture exists; use --refine-initial to replace it")
        if old:
            # Repair only the initial same-session fixtures. No imported or live
            # learner attempts may be rewritten as a side effect of refinement.
            foreign = await repo.fetch_one(
                """SELECT e.id FROM enrollments e JOIN users u ON u.id=e.student_id
                   WHERE e.course_id=:course AND u.username<>:username LIMIT 1""",
                {"course": old["id"], "username": f"catalog_student_{index:02d}"},
            )
            later = await repo.fetch_one(
                """SELECT a.id FROM exam_attempts a JOIN exams e ON e.id=a.exam_id
                   WHERE e.course_id=:course AND a.attempt_no>1 LIMIT 1""",
                {"course": old["id"]},
            )
            if foreign or later:
                raise ValueError("Catalog course has new learner activity; refinement refused")
        description = (
            f"Khóa học nội bộ: {course.title}. Mức độ: nhập môn. "
            f"Thời lượng dự kiến do LMS thiết kế: 4 giờ tự học. Yêu cầu: {course.prerequisite}\n"
            f"Mục tiêu: {'; '.join(q.topic for q in course.questions)}.\n"
            f"Thực hành: {course.assignment}\n"
            "Đánh giá: 3 câu hỏi, 10 điểm/câu, 15 phút, đạt từ 18/30; tối đa 3 lần. "
            "Đây là bài kiểm tra nội bộ, không phải kỳ thi chứng chỉ của nhà cung cấp.\n"
            f"Tài liệu gốc: {course.source_title}: {course.source_url}"
        )
        cid = await upsert_fixture(
            repo,
            "courses",
            {"code": code},
            {
                "title": course.title,
                "description": description,
                "status": "PUBLISHED",
                "created_by": instructor_id,
            },
        )
        uid = students[index - 1]
        await upsert_fixture(
            repo,
            "course_staff",
            {"course_id": cid, "user_id": instructor_id},
            {"role": "INSTRUCTOR"},
        )
        await upsert_fixture(
            repo,
            "completion_rules",
            {"course_id": cid},
            {
                "required_lesson_percent": 100,
                "updated_by": instructor_id,
                "require_submitted_assignments": True,
                "require_published_assignment_grades": True,
                "require_published_exam_grades": True,
                "minimum_grade_percent": 60,
            },
        )
        enrollment = await upsert_fixture(
            repo, "enrollments", {"course_id": cid, "student_id": uid}, {"status": "ACTIVE"}
        )
        lessons = []
        for position, module_title in enumerate(
            ("Kiến thức nền tảng", "Ứng dụng và tự đánh giá"), 1
        ):
            mid = await upsert_fixture(
                repo, "modules", {"course_id": cid, "position": position}, {"title": module_title}
            )
            for lesson_no in (1, 2):
                number = (position - 1) * 2 + lesson_no
                question = course.questions[number - 1] if number <= 3 else None
                title = question.topic if question else "Bài thực hành và tiêu chí đánh giá"
                content = (
                    f"Mục tiêu: giải thích {question.topic.lower()}.\n{question.explanation}\n"
                    f"Tự kiểm tra: {question.prompt}\nLời giải: {question.correct}."
                    if question
                    else f"Yêu cầu: {course.assignment}\nRubric: đáp ứng yêu cầu 40 điểm; "
                    "giải thích đúng 30 điểm; minh chứng và kiểm chứng 30 điểm. "
                    "Nêu giả định, cách tái lập và hạn chế; không sao chép dữ liệu cá nhân."
                )
                content += f"\nĐọc thêm: {course.source_title}\n{course.source_url}"
                lid = await upsert_fixture(
                    repo,
                    "lessons",
                    {"module_id": mid, "position": lesson_no},
                    {
                        "title": title,
                        "lesson_type": "ARTICLE",
                        "is_preview": number == 1,
                        "content": content,
                    },
                )
                lessons.append(lid)
                await upsert_fixture(
                    repo,
                    "lesson_resources",
                    {"lesson_id": lid, "title": course.source_title, "resource_type": "LINK"},
                    {"location": course.source_url},
                )
                completed = number <= 2
                await upsert_fixture(
                    repo,
                    "lesson_progress",
                    {"enrollment_id": enrollment, "lesson_id": lid},
                    {
                        "status": "COMPLETED" if completed else "NOT_STARTED",
                        "last_position_seconds": 0,
                        "started_at": started if completed else None,
                        "completed_at": submitted if completed else None,
                    },
                )

        old_assignment = await repo.fetch_one(
            "SELECT id FROM assignments WHERE course_id=:course ORDER BY id LIMIT 1",
            {"course": cid},
        )
        assignment_key = {"id": old_assignment["id"]} if old_assignment else {"course_id": cid}
        assignment = await upsert_fixture(
            repo,
            "assignments",
            assignment_key,
            {
                "course_id": cid,
                "title": f"Bài thực hành {course.title}",
                "description": course.assignment
                + "\nRubric: yêu cầu 40; giải thích 30; minh chứng 30.",
                "status": "PUBLISHED",
                "opens_at": opens,
                "due_at": due,
                "allow_late": True,
                "late_until": due + timedelta(days=7),
                "max_attempts": 2,
                "max_file_bytes": 10485760,
                "allowed_mime_types": "application/pdf,text/plain",
                "max_score": 100,
                "created_by": instructor_id,
            },
        )
        answer = (
            f"BÀI NỘP MÔ PHỎNG — {course.title}\nYêu cầu: {course.assignment}\n"
            + "\n".join(f"{q.topic}: {q.explanation}" for q in course.questions)
            + f"\nNguồn tham khảo: {course.source_url}\n"
        )
        submission = await upsert_fixture(
            repo,
            "assignment_submissions",
            {"assignment_id": assignment, "enrollment_id": enrollment, "version": 1},
            {
                "status": "SUBMITTED",
                "answer_text": answer,
                "submitted_at": submitted,
                "submitted_by": uid,
            },
        )
        content = answer.encode("utf-8")
        relative = f"submissions/catalog20/{index:02d}.txt"
        digest, path = await create_private_file(settings, relative, content, created_files)
        validate_file_content(path, "text/plain")
        scanner = await scan_file(path, settings)
        await upsert_fixture(
            repo,
            "submission_files",
            {"submission_id": submission, "title": f"Bai-thuc-hanh-{index:02d}.txt"},
            {
                "location": relative,
                "mime_type": "text/plain",
                "size_bytes": len(content),
                "sha256": digest,
                "scan_status": "CLEAN",
                "scan_engine": scanner,
                "scanned_at": now,
            },
        )

        bank = await upsert_fixture(
            repo,
            "question_banks",
            {"course_id": cid, "name": f"CATALOG20_BANK_{index:02d}"},
            {"description": course.source_url, "status": "PUBLISHED", "created_by": instructor_id},
        )
        category = await upsert_fixture(
            repo, "question_categories", {"bank_id": bank, "name": "Kiến thức cốt lõi"}, {}
        )
        existing_questions = await repo.fetch_all(
            "SELECT id FROM questions WHERE bank_id=:bank ORDER BY id", {"bank": bank}
        )
        snapshot = []
        for number, question in enumerate(course.questions, 1):
            values = {
                "bank_id": bank,
                "question_type": "SINGLE",
                "prompt": question.prompt,
                "explanation": question.explanation + "\nNguồn: " + course.source_url,
                "points": 10,
                "status": "PUBLISHED",
                "category_id": category,
                "difficulty": "MEDIUM",
            }
            if number <= len(existing_questions):
                qid = await upsert_fixture(
                    repo, "questions", {"id": existing_questions[number - 1]["id"]}, values
                )
            else:
                qid = await upsert_fixture(
                    repo,
                    "questions",
                    {"bank_id": bank, "prompt": question.prompt},
                    {k: v for k, v in values.items() if k not in {"bank_id", "prompt"}},
                )
            choices = [question.correct, *question.wrong]
            offset = (index + number) % 3
            choices = choices[offset:] + choices[:offset]
            options = []
            for key, choice in zip("ABC", choices, strict=True):
                option_id = await upsert_fixture(
                    repo,
                    "question_options",
                    {"question_id": qid, "option_key": key},
                    {"option_text": choice, "is_correct": choice == question.correct},
                )
                options.append(
                    {
                        "id": option_id,
                        "option_key": key,
                        "option_text": choice,
                        "is_correct": choice == question.correct,
                    }
                )
            snapshot.append(
                {
                    "id": qid,
                    "prompt": question.prompt,
                    "question_type": "SINGLE",
                    "points": 10,
                    "options": options,
                }
            )
        old_exam = await repo.fetch_one(
            "SELECT id FROM exams WHERE course_id=:course", {"course": cid}
        )
        match = {"id": old_exam["id"]} if old_exam else {"course_id": cid}
        exam = await upsert_fixture(
            repo,
            "exams",
            match,
            {
                "course_id": cid,
                "title": f"Kiểm tra nền tảng — {course.title}",
                "instructions": "3 câu trắc nghiệm, mỗi câu một đáp án đúng, 10 điểm/câu. "
                "Thời gian 15 phút; đạt từ 18/30; tối đa 3 lần. Không trừ điểm câu sai; "
                "có thể tiếp tục khi mất kết nối. "
                "Bài nội bộ biên soạn từ tài liệu chính thức, không phải đề thi chứng chỉ.",
                "status": "PUBLISHED",
                "opens_at": opens,
                "due_at": due,
                "duration_seconds": 900,
                "max_attempts": 3,
                "shuffle_questions": True,
                "show_results": True,
                "pass_score": 18,
                "created_by": instructor_id,
                "allow_resume": True,
            },
        )
        await upsert_fixture(
            repo,
            "exam_blueprints",
            {"exam_id": exam, "question_type": "SINGLE"},
            {
                "question_count": 3,
                "points_each": 10,
                "bank_id": bank,
                "category_id": category,
                "difficulty": "MEDIUM",
            },
        )
        for number, question in enumerate(snapshot, 1):
            await upsert_fixture(
                repo,
                "exam_questions",
                {"exam_id": exam, "question_id": question["id"]},
                {"position": number, "points": 10},
            )
        attempt = await upsert_fixture(
            repo,
            "exam_attempts",
            {"exam_id": exam, "enrollment_id": enrollment, "attempt_no": 1},
            {
                "status": "SUBMITTED",
                "started_at": started,
                "expires_at": started + timedelta(minutes=15),
                "submitted_at": submitted,
                "score": 30,
                "max_score": 30,
                "server_version": 4,
                "question_snapshot": encoded(snapshot),
                "graded_at": submitted,
            },
        )
        for question in snapshot:
            selected = [option["id"] for option in question["options"] if option["is_correct"]]
            await upsert_fixture(
                repo,
                "exam_answers",
                {"attempt_id": attempt, "question_id": question["id"]},
                {
                    "selected_option_ids": encoded(selected),
                    "is_correct": True,
                    "points_awarded": 10,
                    "answered_at": submitted,
                },
            )
        await upsert_fixture(
            repo,
            "attempt_events",
            {"attempt_id": attempt, "client_event_id": str(uuid5(NAMESPACE_URL, f"{trace}-event"))},
            {
                "event_type": "TAB_HIDDEN",
                "trace_id": trace,
                "review_status": "DISMISSED",
                "version": 2,
                "reviewed_by": instructor_id,
                "reviewed_at": now,
                "review_note": "Sự kiện mô phỏng phục vụ demo; không phải bằng chứng gian lận.",
            },
        )
        grades = GradeRepository(connection)
        for kind, aid, score, maximum, source_s, source_a, items in (
            (
                "ASSIGNMENT",
                assignment,
                88,
                100,
                submission,
                None,
                [
                    ("requirements", "Đáp ứng yêu cầu", 40, 40),
                    ("explanation", "Giải thích", 30, 30),
                    ("evidence", "Minh chứng", 18, 30),
                ],
            ),
            (
                "EXAM",
                exam,
                30,
                30,
                None,
                attempt,
                [(str(q["id"]), q["prompt"], 10, 10) for q in snapshot],
            ),
        ):
            grade = await upsert_fixture(
                repo,
                "gradebook_entries",
                {"enrollment_id": enrollment, "assessment_type": kind, "assessment_id": aid},
                {
                    "score": score,
                    "max_score": maximum,
                    "status": "PUBLISHED",
                    "graded_by": instructor_id,
                    "published_at": now,
                    "feedback": "Kết quả mô phỏng phục vụ demo LMS.",
                    "version": 1,
                    "source_attempt_id": source_a,
                    "source_submission_id": source_s,
                },
            )
            await grades.replace_items(
                grade,
                [
                    {"item_key": key, "label": label, "score": value, "max_score": max_value}
                    for key, label, value, max_value in items
                ],
            )
            detail = await grades.detail(grade)
            await upsert_fixture(
                repo,
                "grade_history",
                {"grade_id": grade, "version": 1},
                {
                    "action": "PUBLISH",
                    "actor_id": instructor_id,
                    "reason": "Dữ liệu kết quả mô phỏng, không phải điểm học viên thật.",
                    "snapshot": encoded(detail),
                },
            )
        await upsert_fixture(
            repo,
            "course_progress",
            {"enrollment_id": enrollment},
            {
                "completed_lessons": 2,
                "total_lessons": 4,
                "progress_percent": 50,
                "completed_at": None,
                "completed_assignments": 1,
                "total_assignments": 1,
                "passed_assignments": 1,
                "total_exams": 1,
                "passed_exams": 1,
            },
        )

        forum = await upsert_fixture(
            repo,
            "forums",
            {"course_id": cid},
            {
                "title": f"Hỏi đáp — {course.title}",
                "description": "Thảo luận mô phỏng; trích nguồn khi trả lời.",
                "created_by": instructor_id,
            },
        )
        thread = await upsert_fixture(
            repo,
            "threads",
            {"forum_id": forum, "title": "Trao đổi trước kỳ kiểm tra"},
            {
                "author_id": uid,
                "body": f"Mình đang ôn chủ đề {course.questions[0].topic}. "
                "Nên chú ý nguyên tắc nào?",
            },
        )
        await upsert_fixture(
            repo,
            "messages",
            {"thread_id": thread, "author_id": instructor_id},
            {"body": course.questions[0].explanation + "\n" + course.source_url},
        )
        await upsert_fixture(
            repo,
            "forum_membership_requests",
            {"course_id": cid, "user_id": uid},
            {
                "status": "APPROVED",
                "reason": "Ghi danh mô phỏng đã được duyệt.",
                "reviewed_by": instructor_id,
                "reviewed_at": now,
            },
        )
        notice = await upsert_fixture(
            repo,
            "notifications",
            {"recipient_id": uid, "resource_id": exam, "type": "CATALOG20_READY"},
            {
                "course_id": cid,
                "title": "Bài kiểm tra nội bộ đã sẵn sàng",
                "body": f"Ôn tập {course.title}: 3 câu, 15 phút.",
                "resource_type": "exam",
            },
        )
        await upsert_fixture(
            repo,
            "notification_deliveries",
            {"notification_id": notice, "channel": "EMAIL"},
            {
                "recipient_id": uid,
                "status": "FAILED",
                "last_error": "SEED_EMAIL_DISABLED",
                "attempt_count": 0,
                "sent_at": None,
                "available_at": now,
            },
        )
        csv_content = csv_bytes(
            LEARNER_COLUMNS,
            [
                {
                    "enrollment_id": enrollment,
                    "student_id": uid,
                    "username": f"catalog_student_{index:02d}",
                    "status": "ACTIVE",
                    "progress_percent": 50,
                    "completed_at": None,
                    "published_grades": 2,
                    "draft_grades": 0,
                }
            ],
        )
        location = f"exports/catalog20-{index:02d}.csv"
        await create_private_file(settings, location, csv_content, created_files)
        await upsert_fixture(
            repo,
            "export_jobs",
            {"requested_by": instructor_id, "request_id": str(uuid5(NAMESPACE_URL, trace))},
            {
                "kind": "LEARNERS",
                "course_id": cid,
                "filters": "{}",
                "status": "READY",
                "location": location,
                "row_count": 1,
                "trace_id": trace,
                "completed_at": now,
                "attempt_count": 1,
                "available_at": now,
            },
        )
        await AuditRepository(connection).append_log(
            actor_id=instructor_id,
            action="catalog20.seed",
            resource="course",
            resource_id=str(cid),
            trace_id=trace,
            details={
                "dataset": "catalog20/v2",
                "simulated_activity": True,
                "source": course.source_url,
                "question_count": 3,
                "max_score": 30,
            },
        )
        seeded += 1
    return {"courses_seeded": seeded, "courses_preserved": 20 - seeded, "student_ids": students}


async def record_demo_logins(engine, settings, password):
    """Produce actual successful authentication events, then revoke all new sessions."""
    app = create_app(settings)
    app.state.db_engine = engine
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://catalog20.local"
    ) as client:
        for index in range(1, 21):
            trace = f"{TRACE}-login-{index:02d}"
            async with engine.connect() as connection:
                existing = await SqlRepository(connection).fetch_one(
                    "SELECT id FROM security_events WHERE trace_id=:trace", {"trace": trace}
                )
            if existing:
                continue
            response = await client.post(
                "/api/v1/auth/login",
                headers={"X-Trace-ID": trace},
                json={"login": f"catalog_student_{index:02d}", "password": password},
            )
            if response.status_code != 200:
                raise ValueError("Catalog account password changed; authentication refused")
            refresh = response.json()["data"]["refresh_token"]
            logout = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
            logout.raise_for_status()


async def run(args):
    settings = Settings()
    if settings.app_env not in {"development", "test"}:
        raise ValueError("Only development/test may contain demo learning activity")
    database = settings.sqlalchemy_url.database or ""
    allowed = database.startswith(("lms_demo_", "lms_test_"))
    if not allowed and not (args.allow_lms and database == "lms"):
        raise ValueError("Use --allow-lms for the authorized local lms database")
    engine = build_engine(settings)
    created_files = []
    try:
        if args.apply:
            try:
                async with engine.begin() as connection:
                    teacher = await SqlRepository(connection).fetch_one(
                        """SELECT id FROM users WHERE username='demo_instructor'
                           AND status='ACTIVE' AND deleted_at IS NULL"""
                    )
                    if teacher is None:
                        raise ValueError("Bootstrap demo_instructor before running the seed")
                    summary = await seed_catalog(
                        connection,
                        settings,
                        instructor_id=teacher["id"],
                        created_files=created_files,
                        refine_initial=args.refine_initial,
                    )
            except BaseException:
                for path in reversed(created_files):
                    path.unlink(missing_ok=True)
                raise
            await record_demo_logins(engine, settings, CATALOG_PASSWORD)
            print(encoded({"database": database, **summary}))
        from scripts.verify_catalog20 import verify_catalog

        report = await verify_catalog(engine, settings)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, default=str, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Verified {len(report['tables'])} tables; report: {args.report}")
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-lms", action="store_true")
    parser.add_argument(
        "--refine-initial",
        action="store_true",
        help="Replace the initial unverified CATALOG20 fixtures only",
    )
    parser.add_argument("--report", type=Path, default=Path("../docs/data/catalog20-report.json"))
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
