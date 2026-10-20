# WBS 7.5 — Notification delivery and email adapter

Notifications remain an in-app record first. Users can opt in to email delivery
at `GET/PUT /api/v1/notifications/preferences`; the preference may allow all event
types or an explicit allow-list. Each opted-in notification creates one durable
`notification_deliveries` outbox row with a unique `(notification_id, channel)` key.

The worker locks one due row in a transaction, sends through the SMTP adapter off
the event loop, and marks the row `SENT` before releasing the lock. Temporary I/O,
timeout and 4xx SMTP failures use bounded exponential retry; permanent failures
become `FAILED` with a redacted error code. A process restart rolls back an
in-flight send to `PENDING`; the stable Message-ID lets a provider deduplicate an
at-least-once retry. Set
`EMAIL_DELIVERY_ENABLED=false` for local development, or point SMTP settings at a
local test server before enabling it. No credential is written to logs.

Evidence: migration `0016_week7_hardening`, notification preference API, the
`notification.email.*` audit actions and the worker's unique outbox claim.
