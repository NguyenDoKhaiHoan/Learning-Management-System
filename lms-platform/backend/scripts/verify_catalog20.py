"""Read-only catalog coverage, referential, grading, snapshot and file verification."""

import hashlib
import json
from datetime import UTC, datetime

from scripts.seed_catalog20 import REFERENCE_TABLES
from src.core.database.sql import SqlRepository


async def verify_catalog(engine, settings):
    async with engine.connect() as connection:
        repo = SqlRepository(connection)
        tables = await repo.fetch_all(
            """SELECT TABLE_NAME name FROM information_schema.TABLES
               WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"""
        )
        counts = {}
        for row in tables:
            table = row["name"]
            result = await repo.fetch_one(f"SELECT COUNT(*) n FROM `{table}`")
            counts[table] = {
                "rows": result["n"],
                "minimum": None if table in REFERENCE_TABLES else 20,
            }
            if table in REFERENCE_TABLES:
                counts[table]["exception"] = REFERENCE_TABLES[table]
            else:
                assert result["n"] >= 20, f"{table} has fewer than 20 rows"
        foreign_keys = await repo.fetch_all(
            """SELECT TABLE_NAME child,COLUMN_NAME col,REFERENCED_TABLE_NAME parent,
                      REFERENCED_COLUMN_NAME parent_col
               FROM information_schema.KEY_COLUMN_USAGE
               WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL"""
        )
        for fk in foreign_keys:
            row = await repo.fetch_one(
                f"SELECT COUNT(*) n FROM `{fk['child']}` c LEFT JOIN `{fk['parent']}` p "
                f"ON c.`{fk['col']}`=p.`{fk['parent_col']}` "
                f"WHERE c.`{fk['col']}` IS NOT NULL AND p.`{fk['parent_col']}` IS NULL"
            )
            assert row["n"] == 0, f"Foreign-key orphan in {fk['child']}"
        courses = await repo.fetch_all(
            "SELECT id,code,title,description FROM courses "
            "WHERE code LIKE 'CATALOG20\\_%' ORDER BY code"
        )
        assert len(courses) == 20
        course_reports = []
        for course in courses:
            cid = course["id"]
            lessons = await repo.fetch_all(
                """SELECT l.id,l.content FROM lessons l JOIN modules m ON m.id=l.module_id
                   WHERE m.course_id=:course AND l.deleted_at IS NULL""",
                {"course": cid},
            )
            assert len(lessons) == 4 and all(lesson["content"] for lesson in lessons)
            exam = await repo.fetch_one(
                "SELECT * FROM exams WHERE course_id=:course", {"course": cid}
            )
            questions = await repo.fetch_all(
                """SELECT q.id,q.question_type,q.prompt,q.explanation,eq.points
                   FROM questions q JOIN exam_questions eq ON eq.question_id=q.id
                   WHERE eq.exam_id=:exam ORDER BY eq.position""",
                {"exam": exam["id"]},
            )
            assert len(questions) == 3
            maximum = sum(q["points"] for q in questions)
            assert maximum == 30 and exam["pass_score"] == 18
            assert exam["duration_seconds"] == 900 and exam["opens_at"] < exam["due_at"]
            for question in questions:
                options = await repo.fetch_all(
                    "SELECT id,is_correct FROM question_options WHERE question_id=:question",
                    {"question": question["id"]},
                )
                assert len(options) == 3 and sum(o["is_correct"] for o in options) == 1
                assert "https://" in question["explanation"]
            attempt = await repo.fetch_one(
                "SELECT * FROM exam_attempts WHERE exam_id=:exam AND attempt_no=1",
                {"exam": exam["id"]},
            )
            snapshot = json.loads(attempt["question_snapshot"])
            assert {q["id"] for q in snapshot} == {q["id"] for q in questions}
            assert all(len(q["options"]) == 3 for q in snapshot)
            answers = await repo.fetch_all(
                "SELECT * FROM exam_answers WHERE attempt_id=:attempt", {"attempt": attempt["id"]}
            )
            assert len(answers) == len(snapshot)
            score = 0
            for question in snapshot:
                answer = next(a for a in answers if a["question_id"] == question["id"])
                selected = set(json.loads(answer["selected_option_ids"]))
                key = {option["id"] for option in question["options"] if option["is_correct"]}
                assert all(type(option_id) is int for option_id in selected)
                correct = selected == key
                awarded = question["points"] if correct else 0
                assert answer["points_awarded"] == awarded and bool(answer["is_correct"]) == correct
                score += awarded
            assert attempt["score"] == score == 30 and attempt["max_score"] == maximum
            assert attempt["started_at"] < attempt["submitted_at"] <= attempt["expires_at"]
            grades = await repo.fetch_all(
                "SELECT * FROM gradebook_entries WHERE enrollment_id=:enrollment",
                {"enrollment": attempt["enrollment_id"]},
            )
            assert len(grades) == 2
            for grade in grades:
                totals = await repo.fetch_one(
                    "SELECT SUM(score) score,SUM(max_score) maximum "
                    "FROM grade_items WHERE grade_id=:id",
                    {"id": grade["id"]},
                )
                assert totals["score"] == grade["score"]
                assert totals["maximum"] == grade["max_score"]
                history = await repo.fetch_one(
                    "SELECT snapshot FROM grade_history WHERE grade_id=:id AND version=:version",
                    {"id": grade["id"], "version": grade["version"]},
                )
                data = json.loads(history["snapshot"])
                assert str(data["score"]) == str(grade["score"])
                if grade["assessment_type"] == "EXAM":
                    assert grade["source_attempt_id"] == attempt["id"]
                    assert grade["score"] == attempt["score"]
                    assert grade["max_score"] == attempt["max_score"]
            progress = await repo.fetch_one(
                "SELECT * FROM course_progress WHERE enrollment_id=:enrollment",
                {"enrollment": attempt["enrollment_id"]},
            )
            assert progress["progress_percent"] == 50 and progress["completed_lessons"] == 2
            assert progress["total_lessons"] == 4 and progress["completed_at"] is None
            assert progress["completed_assignments"] == progress["passed_assignments"] == 1
            assert progress["total_exams"] == progress["passed_exams"] == 1
            course_reports.append(
                {
                    "code": course["code"],
                    "title": course["title"],
                    "lessons": len(lessons),
                    "exam_questions": len(questions),
                    "exam_max_score": int(maximum),
                    "pass_score": 18,
                }
            )
        files = await repo.fetch_all(
            """SELECT location,size_bytes,sha256,scan_status FROM submission_files
               WHERE location LIKE 'submissions/catalog20/%'"""
        )
        assert len(files) == 20
        root = settings.private_storage_root.resolve()
        for row in files:
            path = (root / row["location"]).resolve()
            assert path.is_relative_to(root) and path.is_file()
            content = path.read_bytes()
            assert row["scan_status"] == "CLEAN"
            assert len(content) == row["size_bytes"]
            assert hashlib.sha256(content).hexdigest() == row["sha256"]
        exports = await repo.fetch_all(
            "SELECT location FROM export_jobs WHERE trace_id LIKE 'catalog20-v2-%'"
        )
        assert len(exports) == 20
        for row in exports:
            path = (root / row["location"]).resolve()
            assert path.is_relative_to(root) and path.is_file()
            assert len(path.read_text(encoding="utf-8-sig").splitlines()) == 2
    return {
        "database": settings.sqlalchemy_url.database,
        "verified_at": datetime.now(UTC).isoformat(),
        "tables": counts,
        "foreign_keys_checked": len(foreign_keys),
        "courses": course_reports,
        "questions": 60,
        "exam_options": 180,
        "private_submission_files_verified": len(files),
        "export_files_verified": len(exports),
        "data_classification": "Internal teaching content with primary references; "
        "simulated learner activity.",
    }
