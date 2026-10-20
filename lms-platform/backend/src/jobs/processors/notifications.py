"""Transactional outbox: row locks serialize workers; SMTP is at-least-once."""

import asyncio
import json
import logging
import smtplib
from typing import Protocol

from src.config.config import Settings
from src.core.database.sql import SqlRepository
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.notification.infrastructure.email import OutboundEmail, SmtpEmailAdapter

logger = logging.getLogger("lms")


class EmailAdapter(Protocol):
    async def send(self, message: OutboundEmail) -> None: ...


def retryable(error: Exception) -> bool:
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return all(400 <= code < 500 for code, _ in error.recipients.values())
    if isinstance(error, smtplib.SMTPResponseException):
        return 400 <= error.smtp_code < 500
    return isinstance(error, (OSError, TimeoutError, smtplib.SMTPServerDisconnected))


async def process_notification_emails(
    engine, settings: Settings, *, adapter: EmailAdapter | None = None, batch_size: int = 20
) -> int:
    if not settings.email_delivery_enabled:
        return 0
    adapter = adapter or SmtpEmailAdapter(settings)
    processed = 0
    for _ in range(max(0, min(batch_size, 100))):
        # Keep the row lock across SMTP. A restart rolls back to PENDING; another
        # worker skips the locked row. Never commit PROCESSING without a lease.
        async with engine.begin() as connection:
            repo = SqlRepository(connection)
            job = await repo.fetch_one(
                """SELECT id,notification_id,recipient_id,attempt_count
                   FROM notification_deliveries
                   WHERE status='PENDING' AND available_at<=UTC_TIMESTAMP(6)
                   ORDER BY available_at,id LIMIT 1 FOR UPDATE SKIP LOCKED"""
            )
            if job is None:
                break
            recipient = await repo.fetch_one(
                """SELECT u.email,u.status,u.deleted_at,p.email_enabled,p.event_types,n.type
                   FROM users u JOIN notifications n ON n.id=:notification
                   LEFT JOIN notification_preferences p ON p.user_id=u.id
                   WHERE u.id=:user""",
                {"notification": job["notification_id"], "user": job["recipient_id"]},
            )
            events = recipient["event_types"] if recipient else None
            if isinstance(events, str):
                events = json.loads(events)
            enabled = recipient and recipient["status"] == "ACTIVE" and (
                recipient["deleted_at"] is None and recipient["email_enabled"]
                and (events is None or recipient["type"] in events)
            )
            attempt = int(job["attempt_count"]) + 1
            code, action, status, delay = None, "sent", "SENT", 0
            if not enabled:
                code, action, status = "DELIVERY_DISABLED", "suppressed", "FAILED"
            else:
                try:
                    # Keep private course names, grades and answers inside the
                    # authenticated inbox even when a user's course access changes.
                    await adapter.send(OutboundEmail(
                        recipient=recipient["email"],
                        subject="LMS: Bạn có thông báo mới",
                        body="Đăng nhập LMS và mở Thông báo để xem thông tin mới.",
                        message_id=f"<lms-notification-{job['notification_id']}@lms.local>",
                    ))
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    retry = retryable(error) and attempt < settings.email_max_attempts
                    status, action = ("PENDING", "retry") if retry else ("FAILED", "failed")
                    code = "EMAIL_RETRY" if retry else "EMAIL_FAILED"
                    delay = min(settings.email_retry_base_seconds * 2 ** (attempt - 1), 3600)
            await repo.execute(
                """UPDATE notification_deliveries SET status=:status,
                   attempt_count=attempt_count+1,last_error=:code,
                   available_at=TIMESTAMPADD(SECOND,:delay,UTC_TIMESTAMP(6)),
                   sent_at=IF(:status='SENT',UTC_TIMESTAMP(6),NULL) WHERE id=:id""",
                {"id": job["id"], "status": status, "code": code, "delay": delay},
            )
            await AuditRepository(connection).append_log(
                actor_id=None, action="notification.email." + action,
                resource="notification_delivery", resource_id=str(job["id"]),
                trace_id="notification-worker", details={"attempt": attempt, "code": code},
            )
            logger.info("notification_delivery", extra={
                "event": "notification_delivery", "trace_id": "notification-worker",
                "job_type": "email", "job_status": status,
            })
        processed += 1
    return processed


async def run_notification_email_worker(engine, settings: Settings):
    while True:
        try:
            await process_notification_emails(engine, settings)
        except Exception as error:
            logger.error("notification_worker_failed", extra={
                "event": "worker_failed", "job_type": "email",
                "exception_type": type(error).__name__,
            })
        await asyncio.sleep(settings.email_worker_interval_seconds)
