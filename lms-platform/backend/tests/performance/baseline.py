"""Opt-in HTTP/SQL/job baseline on a disposable MySQL schema.

Run with pytest tests/performance/baseline.py -s --require-mysql. Ordinary regression
does not collect this file. BASELINE_OUTPUT optionally saves a portable report.
"""

import asyncio
import json
import math
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from sqlalchemy import event, text

from src.jobs.processors.exports import process_exports
from tests.integration.test_week2_mysql import api as api
from tests.integration.test_week2_mysql import new_content, new_course
from tests.integration.test_week3_learning import activate_student
from tests.integration.test_week6_reports import config, export_body


async def test_performance_baseline(api):
    call, engine, users, _, _ = api
    samples = int(os.getenv("BASELINE_SAMPLES", "40"))
    concurrency = int(os.getenv("BASELINE_CONCURRENCY", "4"))
    assert 10 <= samples <= 1000 and 1 <= concurrency <= 20
    course_ids = []
    for index in range(12):
        cid = (await new_course(call, code=f"PERF{index}"))["id"]
        await new_content(call, cid)
        await call("POST", f"/courses/{cid}/status", json={"status": "PUBLISHED"})
        course_ids.append(cid)
    cid = course_ids[0]
    await activate_student(engine, cid, users["student"])
    async with engine.begin() as connection:
        for index in range(200):
            # MySQL lastrowid belongs to this INSERT, never a shared MAX(id).
            inserted = await connection.execute(
                text("INSERT INTO users(email,username,hashed_password) VALUES "
                     "(:email,:name,'unusable-benchmark-hash')"),
                {"email": f"perf{index}@example.test", "name": f"perf{index}"},
            )
            uid = inserted.lastrowid
            await connection.execute(
                text("INSERT INTO enrollments(course_id,student_id,status) "
                     "VALUES (:course,:student,'ACTIVE')"),
                {"course": cid, "student": uid},
            )
    queries = 0

    def count(*_):
        nonlocal queries
        queries += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count)
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "environment": {"python": platform.python_version(), "os": platform.system(),
                        "transport": "in-process HTTPX ASGI + real MySQL + private disk"},
        "dataset": {"courses": 12, "learners_in_course": 201, "lessons": 12},
        "concurrency": concurrency, "samples_per_endpoint": samples,
        "warmup_per_endpoint": 3, "results": [],
    }
    async with engine.connect() as connection:
        report["environment"]["mysql"] = await connection.scalar(text("SELECT VERSION()"))

    async def measure(label, operation, iterations, workers, budget):
        nonlocal queries
        for _ in range(3):
            await operation()
        queries = 0
        timings = []
        semaphore = asyncio.Semaphore(workers)

        async def once():
            async with semaphore:
                started = perf_counter()
                await operation()  # Unexpected HTTP status/job outcome fails the run.
                timings.append((perf_counter() - started) * 1000)

        started = perf_counter()
        await asyncio.gather(*(once() for _ in range(iterations)))
        elapsed = perf_counter() - started
        timings.sort()
        result = {"operation": label, "samples": iterations, "errors": 0,
                  "p50_ms": round(timings[math.ceil(iterations * .5) - 1], 2),
                  "p95_ms": round(timings[math.ceil(iterations * .95) - 1], 2),
                  "max_ms": round(timings[-1], 2),
                  "operations_per_second": round(iterations / elapsed, 2),
                  "sql_per_operation": round(queries / iterations, 2),
                  "p95_budget_ms": budget}
        report["results"].append(result)

    try:
        for label, path, actor in (
            ("course_catalog", "/courses?limit=20", "student"),
            ("student_progress", f"/courses/{cid}/progress/me", "student"),
            ("learner_report", f"/reports/courses/{cid}/learners?limit=20", "owner"),
            ("gradebook_report", f"/reports/courses/{cid}/gradebook", "owner"),
            ("admin_overview", "/reports/overview", "admin"),
        ):
            async def request(path=path, actor=actor):
                await call("GET", path, actor=actor)

            await measure(label, request, samples, concurrency, 1000)

        async def export():
            job = await call("POST", "/exports", expected=202,
                             json=export_body(cid, "LEARNERS"))
            assert await process_exports(engine, config(api)) == 1
            ready = await call("GET", f"/exports/{job['id']}")
            assert ready["status"] == "READY" and ready["row_count"] == 201

        await measure("learner_export_201_rows", export, 10, 1, 2000)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count)
    report["passed"] = all(r["p95_ms"] <= r["p95_budget_ms"] for r in report["results"])
    output = os.getenv("BASELINE_OUTPUT")
    if output:
        Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    assert report["passed"], "Performance budget exceeded; inspect the saved report"
