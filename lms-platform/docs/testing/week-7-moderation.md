# WBS 7.6 — Forum moderation and membership review

Course managers can list a moderation queue, lock/archive/re-open threads, and
hide/restore replies with an audit record and optional reason. Hidden replies are
excluded from normal thread reads while their rows remain available for review.

`forum_membership_requests` provides a separate review trail for forum access.
Students submit a reason, and an instructor or admin approves or rejects it. An
approved request grants course-scoped forum access without changing course
enrollment. Every query still checks the current account, role and course scope.

Evidence: the moderation and membership endpoints in the forum router, migration
`0016_week7_hardening`, and `forum.thread.moderate`, `forum.message.moderate`,
`forum.membership.*` audit actions.
