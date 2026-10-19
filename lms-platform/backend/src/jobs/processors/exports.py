"""Durable bounded exports; uncommitted jobs remain pending after a restart."""

import asyncio
import json
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from src.core.contracts import CurrentUser
from src.core.database.sql import SqlRepository
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.reporting_export.application.exports import Exports
from src.modules.reporting_export.application.reports import (
    GRADE_COLUMNS,
    LEARNER_COLUMNS,
    OVERVIEW_COLUMNS,
)
from src.modules.reporting_export.application.service import DashboardReports
from src.modules.reporting_export.domain.csv import csv_bytes
from src.modules.user_role.infrastructure.repository import RoleRepository

MAX_EXPORT_ROWS = 10000
logger = logging.getLogger("lms")


def write_csv(path, columns, rows):
    # Serialization and filesystem writes both run off the API event loop.
    return path.write_bytes(csv_bytes(columns, rows))


async def process_exports(engine, settings, batch_size=10):
    async with engine.connect() as connection:
        candidates = await SqlRepository(connection).fetch_all(
            "SELECT id,requested_by,kind,course_id,attempt_count FROM export_jobs "
            "WHERE status='PENDING' AND available_at<=UTC_TIMESTAMP(6) "
            "ORDER BY available_at,id LIMIT :limit",
            {"limit": batch_size},
        )
    processed = 0
    for candidate in candidates:
        path = None
        try:
            async with (
                asyncio.timeout(settings.export_timeout_seconds),
                engine.begin() as connection,
            ):
                repo = SqlRepository(connection)
                await repo.fetch_one(
                    "SELECT id FROM users WHERE id=:id FOR UPDATE",
                    {"id": candidate["requested_by"]},
                )
                user = await IdentityRepository(connection).get_user(candidate["requested_by"])
                roles = RoleRepository(connection)
                grants = await roles.get_permission_codes(candidate["requested_by"])
                if not user or user["status"] != "ACTIVE" or "course.read" not in grants:
                    raise HTTPException(403)
                actor = CurrentUser(
                    id=str(user["id"]),
                    email=user["email"],
                    username=user["username"],
                    roles=tuple(await roles.get_role_codes(user["id"])),
                )
                service = Exports(connection, actor, "export-worker")
                await service.scope_for_export(candidate["kind"], candidate["course_id"])
                job = await repo.fetch_one(
                    "SELECT *,available_at<=UTC_TIMESTAMP(6) AS due FROM export_jobs "
                    "WHERE id=:id FOR UPDATE", {"id": candidate["id"]}
                )
                if job["status"] != "PENDING" or not job["due"]:
                    continue
                candidate["attempt_count"] = job["attempt_count"]
                service.trace_id = job["trace_id"]
                filters = json.loads(job["filters"])
                if job["kind"] == "OVERVIEW":
                    rows = await DashboardReports(connection).courses(actor, admin=True)
                    columns = OVERVIEW_COLUMNS
                elif job["kind"] == "LEARNERS":
                    rows = (
                        await service.learners(job["course_id"], filters, MAX_EXPORT_ROWS + 1, 0)
                    )["items"]
                    columns = LEARNER_COLUMNS
                else:
                    rows = (
                        await service.gradebook(job["course_id"], filters, MAX_EXPORT_ROWS + 1, 0)
                    )["items"]
                    columns = GRADE_COLUMNS
                if len(rows) > MAX_EXPORT_ROWS:
                    raise HTTPException(413)
                location = Path("exports") / (uuid4().hex + ".csv")
                path = settings.private_storage_root.resolve() / location
                path.parent.mkdir(parents=True, exist_ok=True)
                writing = asyncio.create_task(asyncio.to_thread(write_csv, path, columns, rows))
                try:
                    await asyncio.shield(writing)
                except asyncio.CancelledError:
                    # Let the thread close the file before unlinking it on Windows.
                    await writing
                    raise
                await repo.execute(
                    """UPDATE export_jobs SET status='READY',location=:location,row_count=:count,
                    completed_at=UTC_TIMESTAMP(6),attempt_count=attempt_count+1,
                    error_code=NULL WHERE id=:id""",
                    {"id": job["id"], "location": location.as_posix(), "count": len(rows)},
                )
                await service.audit(
                    "export.ready",
                    "export_job",
                    job["id"],
                    details={
                        "kind": job["kind"],
                        "course_id": str(job["course_id"]) if job["course_id"] else None,
                        "row_count": len(rows),
                    },
                )
            processed += 1
        except asyncio.CancelledError:
            if path:
                path.unlink(missing_ok=True)
            raise
        except Exception as error:
            if path:
                path.unlink(missing_ok=True)
            code = (
                "ACCESS_REVOKED"
                if isinstance(error, HTTPException) and error.status_code in (403, 404)
                else (
                    "ROW_LIMIT"
                    if isinstance(error, HTTPException) and error.status_code == 413
                    else "EXPORT_FAILED"
                )
            )
            attempt = candidate["attempt_count"] + 1
            retry = isinstance(error, (OSError, TimeoutError, OperationalError)) and (
                attempt < settings.export_max_attempts
            )
            delay = min(settings.export_retry_base_seconds * 2 ** (attempt - 1), 300)
            async with engine.begin() as connection:
                repo = SqlRepository(connection)
                changed = await repo.execute(
                    """UPDATE export_jobs SET status=:status,error_code=:code,
                    attempt_count=attempt_count+1,
                    available_at=TIMESTAMPADD(SECOND,:delay,UTC_TIMESTAMP(6)),
                    completed_at=IF(:retry=1,NULL,UTC_TIMESTAMP(6))
                    WHERE id=:id AND status='PENDING' AND attempt_count=:previous
                    AND available_at<=UTC_TIMESTAMP(6)""",
                    {"id": candidate["id"], "code": "EXPORT_RETRY" if retry else code,
                     "status": "PENDING" if retry else "FAILED", "retry": retry,
                     "delay": delay if retry else 0, "previous": candidate["attempt_count"]},
                )
                if changed:
                    await AuditRepository(connection).append_log(
                        actor_id=None,
                        action="export.retry" if retry else "export.failed",
                        resource="export_job",
                        resource_id=str(candidate["id"]),
                        trace_id="export-worker",
                        details={"code": code, "attempt": attempt,
                                 "retry_in_seconds": delay if retry else None},
                    )
            processed += bool(changed)
    return processed


async def run_export_worker(engine, settings, interval=2):
    while True:
        try:
            await process_exports(engine, settings)
        except Exception:
            logger.error("Export processing failed; uncommitted jobs remain pending")
        await asyncio.sleep(interval)
