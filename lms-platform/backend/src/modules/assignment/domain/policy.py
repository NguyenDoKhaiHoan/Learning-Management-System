"""Assignment lifecycle and server-time submission policy."""

from datetime import UTC

from fastapi import HTTPException

from src.modules.file_management.domain.policy import ALLOWED_MIME_EXTENSIONS


def normalize_input(body):
    opens = body.opens_at.astimezone(UTC).replace(tzinfo=None)
    due = body.due_at.astimezone(UTC).replace(tzinfo=None)
    late = body.late_until.astimezone(UTC).replace(tzinfo=None) if body.late_until else None
    if opens >= due or (body.allow_late and (late is None or late <= due)):
        raise HTTPException(422, "Invalid assignment time window")
    if not body.allow_late and late is not None:
        raise HTTPException(422, "Late deadline requires allow_late")
    allowed = sorted(set(body.allowed_mime_types))
    if not allowed or any(mime not in ALLOWED_MIME_EXTENSIONS for mime in allowed):
        raise HTTPException(422, "Unsupported file policy")
    return {
        **body.model_dump(exclude={"opens_at", "due_at", "late_until", "allowed_mime_types"}),
        "opens_at": opens,
        "due_at": due,
        "late_until": late,
        "allowed_mime_types": ",".join(allowed),
    }


def submission_status(assignment, now):
    if assignment["status"] != "PUBLISHED" or now < assignment["opens_at"]:
        raise HTTPException(409, "Assignment is not open")
    if now <= assignment["due_at"]:
        return "SUBMITTED"
    if assignment["allow_late"] and now <= assignment["late_until"]:
        return "LATE"
    raise HTTPException(409, "Submission deadline has passed")
