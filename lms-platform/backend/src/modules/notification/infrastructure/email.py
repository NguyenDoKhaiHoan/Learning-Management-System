"""Small email adapter used by the durable notification outbox worker."""

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from src.config.config import Settings


@dataclass(frozen=True)
class OutboundEmail:
    recipient: str
    subject: str
    body: str
    message_id: str


class SmtpEmailAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _send_sync(self, message: OutboundEmail) -> None:
        email = EmailMessage()
        email["From"] = self.settings.email_from
        email["To"] = message.recipient
        email["Subject"] = message.subject
        email["Message-ID"] = message.message_id
        email.set_content(message.body)
        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=self.settings.smtp_timeout_seconds,
        ) as smtp:
            if self.settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if self.settings.smtp_username:
                smtp.login(
                    self.settings.smtp_username,
                    self.settings.smtp_password.get_secret_value()
                    if self.settings.smtp_password
                    else "",
                )
            smtp.send_message(email)

    async def send(self, message: OutboundEmail) -> None:
        sending = asyncio.create_task(asyncio.to_thread(self._send_sync, message))
        try:
            await asyncio.shield(sending)
        except asyncio.CancelledError:
            # smtplib cannot be interrupted. Keep the transaction lock until the
            # thread closes its socket; another worker must not send concurrently.
            await sending
            raise


class MemoryEmailAdapter:
    """Deterministic adapter for tests and local dry-runs."""

    def __init__(self):
        self.messages: list[OutboundEmail] = []

    async def send(self, message: OutboundEmail) -> None:
        self.messages.append(message)
