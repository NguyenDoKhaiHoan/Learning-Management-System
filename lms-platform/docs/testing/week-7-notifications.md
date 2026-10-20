# WBS 7.5 — Notification delivery and email adapter

Notifications remain an in-app record first. Users can opt in to email delivery
at `GET/PUT /api/v1/notifications/preferences`; the preference may allow all event
types or an explicit allow-list. Each opted-in notification creates one durable
`notification_deliveries` outbox row with a unique `(notification_id, channel)` key.

The worker claims rows atomically, sends through the SMTP adapter off the event
loop, and marks the row `SENT`. Temporary I/O, timeout and SMTP failures use
bounded exponential retry; permanent failures become `FAILED` with a redacted
error summary. A process restart can safely resume `PROCESSING` rows. Set
`EMAIL_DELIVERY_ENABLED=false` for local development, or point SMTP settings at a
local test server before enabling it. No credential is written to logs.

Evidence: migration `0016_week7_hardening`, notification preference API, the
`notification.email.*` audit actions and the worker's unique outbox claim.
