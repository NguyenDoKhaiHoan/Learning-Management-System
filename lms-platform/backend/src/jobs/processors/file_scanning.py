"""Controlled backfill for private files quarantined by the scanning migration."""

import asyncio

from fastapi import HTTPException
from sqlalchemy import text

from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.file_management.infrastructure.integrity import verified_private_path
from src.modules.file_management.infrastructure.scanner import scan_file

SOURCES = (
    (
        "lesson_resource",
        "SELECT id,location,size_bytes,sha256 FROM lesson_resources "
        "WHERE resource_type='FILE' AND scan_status='PENDING' ORDER BY id LIMIT :limit",
        """UPDATE lesson_resources SET scan_status=:status,scan_engine=:scanner,
            scanned_at=UTC_TIMESTAMP(6) WHERE id=:id AND scan_status='PENDING'""",
    ),
    (
        "submission_file",
        "SELECT id,location,size_bytes,sha256 FROM submission_files "
        "WHERE scan_status='PENDING' ORDER BY id LIMIT :limit",
        """UPDATE submission_files SET scan_status=:status,scan_engine=:scanner,
            scanned_at=UTC_TIMESTAMP(6) WHERE id=:id AND scan_status='PENDING'""",
    ),
)


async def scan_pending_files(engine, settings, limit=100):
    candidates = []
    async with engine.connect() as connection:
        for resource, select_sql, update_sql in SOURCES:
            rows = (await connection.execute(text(select_sql), {"limit": limit})).mappings()
            candidates.extend((resource, update_sql, dict(row)) for row in rows)
            if len(candidates) >= limit:
                break
    processed = 0
    for resource, update_sql, row in candidates[:limit]:
        status = "CLEAN"
        reason = None
        try:
            path = await asyncio.to_thread(
                verified_private_path,
                settings.private_storage_root,
                row["location"],
                row["size_bytes"],
                row["sha256"],
            )
            scanner = await scan_file(path, settings)
        except HTTPException as error:
            if error.status_code == 503:
                raise
            status = "REJECTED"
            scanner = settings.file_scan_backend
            reason = "MALWARE" if error.status_code == 422 else "INTEGRITY"
        async with engine.begin() as connection:
            changed = (
                await connection.execute(
                    text(update_sql),
                    {"status": status, "scanner": scanner, "id": row["id"]},
                )
            ).rowcount
            if changed:
                await AuditRepository(connection).append_log(
                    actor_id=None,
                    action="file.scan." + status.lower(),
                    resource=resource,
                    resource_id=str(row["id"]),
                    trace_id="file-scan-backfill",
                    details={"scanner": scanner, "reason": reason},
                )
                processed += 1
    return processed
