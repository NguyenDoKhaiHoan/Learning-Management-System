"""Restartable deadline sweeper. Every attempt uses its own atomic transaction."""

import asyncio
import logging

from src.config.config import Settings
from src.core.database.database import build_engine
from src.core.database.sql import SqlRepository
from src.modules.quiz_exam.application.grading import AttemptGrader

logger = logging.getLogger(__name__)


async def sweep_expired(engine, batch_size=100):
    async with engine.connect() as connection:
        candidates = await SqlRepository(connection).fetch_all(
            """SELECT a.id,a.exam_id,a.enrollment_id,e.course_id
            FROM exam_attempts a JOIN exams e ON e.id=a.exam_id
            WHERE a.status='IN_PROGRESS' AND a.expires_at<=UTC_TIMESTAMP(6)
            ORDER BY a.expires_at,a.id LIMIT :limit""",
            {"limit": batch_size},
        )
    count = 0
    for candidate in candidates:
        async with engine.begin() as connection:
            repo = SqlRepository(connection)
            # Same lock order as HTTP writes; overlapping sweepers recheck current state.
            await repo.fetch_one(
                "SELECT id FROM courses WHERE id=:id FOR UPDATE", {"id": candidate["course_id"]}
            )
            await repo.fetch_one(
                "SELECT id FROM enrollments WHERE id=:id FOR UPDATE",
                {"id": candidate["enrollment_id"]},
            )
            await repo.fetch_one(
                "SELECT id FROM exams WHERE id=:id FOR UPDATE", {"id": candidate["exam_id"]}
            )
            attempt = await repo.fetch_one(
                "SELECT * FROM exam_attempts WHERE id=:id FOR UPDATE", {"id": candidate["id"]}
            )
            now = (await repo.fetch_one("SELECT UTC_TIMESTAMP(6) now"))["now"]
            if attempt["status"] == "IN_PROGRESS" and attempt["expires_at"] <= now:
                await AttemptGrader(connection).finalize(attempt, automatic=True)
                count += 1
    return count


async def run_expiry_worker(engine, interval=5):
    while True:
        try:
            await sweep_expired(engine)
        except Exception:
            # Never include SQL parameters, credentials or submitted answers in logs.
            logger.error("Exam expiry sweep failed; uncommitted attempt will be retried")
        await asyncio.sleep(interval)


async def main():
    engine = build_engine(Settings())
    try:
        await run_expiry_worker(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
