"""Durable email delivery worker with bounded retries and idempotent claims."""

import asyncio
import logging
from typing import Protocol

from sqlalchemy.exc import OperationalError

from src.config.config import Settings
from src.core.database.sql import SqlRepository
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.notification.infrastructure.email import OutboundEmail, SmtpEmailAdapter

logger = logging.getLogger("lms")


class EmailAdapter(Protocol):
    async def send(self, message: OutboundEmail) -> None: ...


async def process_notification_emails(
    engine, settings: Settings, *, adapter: EmailAdapter | None = None, batch_size: int = 20
) -> int:
    if not settings.email_delivery_enabled:
        return 0
    adapter = adapter or SmtpEmailAdapter(settings)
    async with engine.connect() as connection:
        candidates = await SqlRepository(connection).fetch_all(
            """SELECT d.id,d.notification_id,d.recipient_id,d.attempt_count,n.title,n.body,u.email
               FROM notification_deliveries d
               JOIN notifications n ON n.id=d.notification_id
               JOIN users u ON u.id=d.recipient_id
               WHERE d.status IN ('PENDING','PROCESSING')
                 AND d.available_at<=UTC_TIMESTAMP(6)
               ORDER BY d.available_at,d.id LIMIT :limit""",
            {"limit": batch_size},
        )
    processed = 0
    for candidate in candidates:
        async with engine.begin() as connection:
            claimed = await SqlRepository(connection).execute(
                """UPDATE notification_deliveries SET status='PROCESSING',
                   attempt_count=attempt_count+1 WHERE id=:id
                   AND status IN ('PENDING','PROCESSING')
                   AND available_at<=UTC_TIMESTAMP(6)""",
                {"id": candidate["id"]},
            )
        if not claimed:
            continue
        attempt = int(candidate["attempt_count"]) + 1
        try:
            await adapter.send(
                OutboundEmail(
                    recipient=candidate["email"],
                    subject=candidate["title"],
                    body=candidate["body"],
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            retry = isinstance(error, (OSError, TimeoutError, OperationalError)) and (
                attempt < settings.email_max_attempts
            )
            delay = min(settings.email_retry_base_seconds * 2 ** (attempt - 1), 3600)
            async with engine.begin() as connection:
                repo = SqlRepository(connection)
                changed = await repo.execute(
                    """UPDATE notification_deliveries SET status=:status,
                       available_at=TIMESTAMPADD(SECOND,:delay,UTC_TIMESTAMP(6)),
                       last_error=:error WHERE id=:id AND status='PROCESSING'""",
                    {
                        "id": candidate["id"],
                        "status": "PENDING" if retry else "FAILED",
                        "delay": delay if retry else 0,
                        "error": str(error)[:500],
                    },
                )
                if changed:
                    await AuditRepository(connection).append_log(
                        actor_id=None,
                        action="notification.email.retry" if retry else "notification.email.failed",
                        resource="notification_delivery",
                        resource_id=str(candidate["id"]),
                        trace_id="notification-worker",
                        details={"attempt": attempt, "retry": retry},
                    )
            processed += bool(changed)
            continue
        async with engine.begin() as connection:
            repo = SqlRepository(connection)
            changed = await repo.execute(
                """UPDATE notification_deliveries SET status='SENT',sent_at=UTC_TIMESTAMP(6),
                   last_error=NULL WHERE id=:id AND status='PROCESSING'""",
                {"id": candidate["id"]},
            )
            if changed:
                await AuditRepository(connection).append_log(
                    actor_id=None,
                    action="notification.email.sent",
                    resource="notification_delivery",
                    resource_id=str(candidate["id"]),
                    trace_id="notification-worker",
                )
        processed += bool(changed)
    return processed


async def run_notification_email_worker(engine, settings: Settings):
    while True:
        try:
            await process_notification_emails(engine, settings)
        except Exception:
            logger.exception("Notification email delivery failed; pending rows remain durable")
        await asyncio.sleep(settings.email_worker_interval_seconds)
