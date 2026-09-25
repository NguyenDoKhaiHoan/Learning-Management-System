"""Assignment management and immutable submission versions."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.assignment.application.service import AssignmentService
from src.modules.assignment.domain.policy import normalize_input
from src.modules.course.presentation.router import Id, Read, Write
from src.modules.file_management.domain.policy import (
    ALLOWED_MIME_EXTENSIONS,
    normalized_mime,
    safe_display_name,
    validate_file_content,
)

router = APIRouter(
    prefix="/api/v1/courses/{course_id}/assignments",
    tags=["Assignments"],
    responses=ERROR_RESPONSES,
)


class AssignmentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=16000)
    opens_at: AwareDatetime
    due_at: AwareDatetime
    allow_late: bool = False
    late_until: AwareDatetime | None = None
    max_attempts: int = Field(default=1, ge=1, le=100)
    max_file_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=1024 * 1024 * 1024)
    allowed_mime_types: list[str] = Field(default_factory=lambda: ["application/pdf"], min_length=1)
    max_score: float = Field(default=100, gt=0, le=999999.99)


class AssignmentOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    id: str
    course_id: str
    title: str
    description: str
    status: str
    opens_at: datetime
    due_at: datetime
    allow_late: bool
    late_until: datetime | None
    max_attempts: int
    max_file_bytes: int
    allowed_mime_types: list[str]
    max_score: float
    created_by: str


class AssignmentTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(PUBLISHED|CLOSED|ARCHIVED)$")


class TextSubmission(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    answer_text: str = Field(min_length=1, max_length=16000)


class SubmissionOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    id: str
    assignment_id: str
    enrollment_id: str
    version: int
    status: str
    answer_text: str | None
    submitted_at: datetime
    submitted_by: str
    student_id: str


class SubmissionFileOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    id: str
    submission_id: str
    title: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


def result(request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


def public_assignment(row):
    return {**row, "allowed_mime_types": row["allowed_mime_types"].split(",")}


@router.get("", dependencies=Read, response_model=SuccessResponse[list[AssignmentOutput]])
async def list_assignments(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    service = AssignmentService(connection, user, request.state.trace_id)
    course = await service.authorize(course_id)
    manager = await service.is_manager(course)
    rows = await service.assignments.fetch_all(
        """SELECT id, course_id, title, description, status, opens_at, due_at,
                  allow_late, late_until, max_attempts, max_file_bytes,
                  allowed_mime_types, max_score, created_by
           FROM assignments WHERE course_id=:course AND deleted_at IS NULL
             AND (:manager=1 OR status IN ('PUBLISHED','CLOSED')) ORDER BY id""",
        {"course": course_id, "manager": manager},
    )
    return result(request, [public_assignment(row) for row in rows])


@router.post(
    "", dependencies=Write, status_code=201, response_model=SuccessResponse[AssignmentOutput]
)
async def create_assignment(
    course_id: Id,
    body: AssignmentInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = AssignmentService(connection, user, request.state.trace_id)
    course = await service.authorize(course_id, write=True)
    if course["status"] == "ARCHIVED":
        raise HTTPException(409)
    values = normalize_input(body)
    assignment_id = await service.assignments.insert(
        """INSERT INTO assignments
           (course_id, title, description, opens_at, due_at, allow_late, late_until,
            max_attempts, max_file_bytes, allowed_mime_types, max_score, created_by)
           VALUES (:course, :title, :description, :opens_at, :due_at, :allow_late,
                   :late_until, :max_attempts, :max_file_bytes, :allowed_mime_types,
                   :max_score, :created_by)""",
        {**values, "course": course_id, "created_by": int(user.id)},
    )
    await service.audit("assignment.create", "assignment", assignment_id)
    await connection.commit()
    return result(
        request, public_assignment(await service.assignments.assignment(course_id, assignment_id))
    )


@router.get("/{assignment_id}", dependencies=Read, response_model=SuccessResponse[AssignmentOutput])
async def get_assignment(
    course_id: Id,
    assignment_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = AssignmentService(connection, user, request.state.trace_id)
    course = await service.authorize(course_id)
    row = await service.assignments.assignment(course_id, assignment_id)
    if row is None or (row["status"] == "DRAFT" and not await service.is_manager(course)):
        raise HTTPException(404)
    return result(request, public_assignment(row))


@router.put(
    "/{assignment_id}", dependencies=Write, response_model=SuccessResponse[AssignmentOutput]
)
async def update_assignment(
    course_id: Id,
    assignment_id: Id,
    body: AssignmentInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = AssignmentService(connection, user, request.state.trace_id)
    row = await service.manager_assignment(course_id, assignment_id, write=True)
    if row["status"] != "DRAFT":
        raise HTTPException(409, "Only draft assignments can be edited")
    values = normalize_input(body)
    await service.assignments.execute(
        """UPDATE assignments SET title=:title, description=:description,
           opens_at=:opens_at, due_at=:due_at, allow_late=:allow_late,
           late_until=:late_until, max_attempts=:max_attempts,
           max_file_bytes=:max_file_bytes, allowed_mime_types=:allowed_mime_types,
           max_score=:max_score WHERE id=:id""",
        {**values, "id": assignment_id},
    )
    await service.audit("assignment.update", "assignment", assignment_id)
    await connection.commit()
    return result(
        request, public_assignment(await service.assignments.assignment(course_id, assignment_id))
    )


@router.post(
    "/{assignment_id}/status", dependencies=Write, response_model=SuccessResponse[AssignmentOutput]
)
async def transition_assignment(
    course_id: Id,
    assignment_id: Id,
    body: AssignmentTransition,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = AssignmentService(connection, user, request.state.trace_id)
    row = await service.manager_assignment(course_id, assignment_id, write=True)
    allowed = {"DRAFT": {"PUBLISHED"}, "PUBLISHED": {"CLOSED"}, "CLOSED": {"ARCHIVED"}}
    if body.status not in allowed.get(row["status"], set()):
        raise HTTPException(409, "Invalid assignment transition")
    course = await service.repo.fetch_one(
        "SELECT status FROM courses WHERE id=:id", {"id": course_id}
    )
    if body.status == "PUBLISHED" and course["status"] != "PUBLISHED":
        raise HTTPException(409, "Course must be published")
    await service.assignments.execute(
        "UPDATE assignments SET status=:status WHERE id=:id",
        {"status": body.status, "id": assignment_id},
    )
    await service.audit("assignment." + body.status.lower(), "assignment", assignment_id)
    await connection.commit()
    return result(
        request, public_assignment(await service.assignments.assignment(course_id, assignment_id))
    )


@router.delete(
    "/{assignment_id}", dependencies=Write, response_model=SuccessResponse[dict[str, str]]
)
async def delete_assignment(
    course_id: Id,
    assignment_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = AssignmentService(connection, user, request.state.trace_id)
    row = await service.manager_assignment(course_id, assignment_id, write=True)
    if row["status"] != "DRAFT":
        raise HTTPException(409, "Only draft assignments can be deleted")
    await service.assignments.execute(
        "UPDATE assignments SET deleted_at=UTC_TIMESTAMP(6) WHERE id=:id", {"id": assignment_id}
    )
    await service.audit("assignment.delete", "assignment", assignment_id)
    await connection.commit()
    return result(request, {"id": str(assignment_id)})


@router.post(
    "/{assignment_id}/submissions",
    dependencies=Read,
    status_code=201,
    response_model=SuccessResponse[SubmissionOutput],
)
async def submit_text(
    course_id: Id,
    assignment_id: Id,
    body: TextSubmission,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    if "STUDENT" not in user.roles:
        raise HTTPException(403)
    service = AssignmentService(connection, user, request.state.trace_id)
    return result(
        request, await service.submit(course_id, assignment_id, answer_text=body.answer_text)
    )


@router.post(
    "/{assignment_id}/submissions/file",
    dependencies=Read,
    status_code=201,
    response_model=SuccessResponse[SubmissionOutput],
)
async def submit_file(
    course_id: Id,
    assignment_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    file_name: Annotated[str, Header(alias="X-File-Name", min_length=1, max_length=255)],
):
    if "STUDENT" not in user.roles:
        raise HTTPException(403)
    service = AssignmentService(connection, user, request.state.trace_id)
    assignment, _ = await service.student_assignment(course_id, assignment_id)
    mime = normalized_mime(request.headers.get("content-type"))
    if mime not in assignment["allowed_mime_types"].split(","):
        raise HTTPException(422, "File MIME is not allowed for this assignment")
    max_bytes = min(assignment["max_file_bytes"], request.app.state.settings.max_upload_bytes)
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > max_bytes):
        raise HTTPException(413, "File exceeds size limit")
    title = safe_display_name(file_name)
    root = request.app.state.settings.private_storage_root.resolve()
    directory = root / "submissions" / str(assignment_id)
    directory.mkdir(parents=True, exist_ok=True)
    relative = (
        Path("submissions") / str(assignment_id) / (uuid4().hex + ALLOWED_MIME_EXTENSIONS[mime])
    )
    final_path = root / relative
    temporary = final_path.with_suffix(final_path.suffix + ".upload")
    digest = hashlib.sha256()
    size = 0
    try:
        with temporary.open("xb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, "File exceeds size limit")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise HTTPException(422, "File must not be empty")
        validate_file_content(temporary, mime)
        temporary.replace(final_path)
        submission = await service.submit(
            course_id,
            assignment_id,
            file={
                "title": title,
                "location": relative.as_posix(),
                "mime_type": mime,
                "size_bytes": size,
                "sha256": digest.hexdigest(),
            },
        )
        return result(request, submission)
    except Exception:
        temporary.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise


@router.get(
    "/{assignment_id}/submissions/mine",
    dependencies=Read,
    response_model=SuccessResponse[list[SubmissionOutput]],
)
async def my_submissions(
    course_id: Id,
    assignment_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = AssignmentService(connection, user, request.state.trace_id)
    _, enrollment = await service.student_assignment(course_id, assignment_id)
    rows = await service.assignments.fetch_all(
        """SELECT s.id,s.assignment_id,s.enrollment_id,s.version,s.status,
                  s.answer_text,s.submitted_at,s.submitted_by,e.student_id
           FROM assignment_submissions s JOIN enrollments e ON e.id=s.enrollment_id
           WHERE s.assignment_id=:assignment AND s.enrollment_id=:enrollment
           ORDER BY s.version""",
        {"assignment": assignment_id, "enrollment": enrollment["id"]},
    )
    return result(request, rows)


@router.get(
    "/{assignment_id}/submissions",
    dependencies=Write,
    response_model=SuccessResponse[list[SubmissionOutput]],
)
async def list_submissions(
    course_id: Id,
    assignment_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = AssignmentService(connection, user, request.state.trace_id)
    await service.manager_assignment(course_id, assignment_id)
    rows = await service.assignments.fetch_all(
        """SELECT s.id,s.assignment_id,s.enrollment_id,s.version,s.status,
                  s.answer_text,s.submitted_at,s.submitted_by,e.student_id
           FROM assignment_submissions s JOIN enrollments e ON e.id=s.enrollment_id
           WHERE s.assignment_id=:assignment ORDER BY e.student_id,s.version""",
        {"assignment": assignment_id},
    )
    return result(request, rows)


async def authorize_submission(course_id, assignment_id, submission_id, request, connection, user):
    service = AssignmentService(connection, user, request.state.trace_id)
    course = await service.authorize(course_id)
    assignment = await service.assignments.assignment(course_id, assignment_id)
    if assignment is None:
        raise HTTPException(404)
    submission = await service.assignments.submission(assignment_id, submission_id)
    if submission is None:
        raise HTTPException(404)
    if not await service.is_manager(course):
        if submission["student_id"] != int(user.id) or assignment["status"] == "DRAFT":
            raise HTTPException(404)
    return service, submission


@router.get(
    "/{assignment_id}/submissions/{submission_id}/files",
    dependencies=Read,
    response_model=SuccessResponse[list[SubmissionFileOutput]],
)
async def list_submission_files(
    course_id: Id,
    assignment_id: Id,
    submission_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service, _ = await authorize_submission(
        course_id, assignment_id, submission_id, request, connection, user
    )
    return result(request, await service.assignments.submission_files(submission_id))


@router.get(
    "/{assignment_id}/submissions/{submission_id}/files/{file_id}/content", dependencies=Read
)
async def download_submission_file(
    course_id: Id,
    assignment_id: Id,
    submission_id: Id,
    file_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service, _ = await authorize_submission(
        course_id, assignment_id, submission_id, request, connection, user
    )
    row = await service.assignments.fetch_one(
        """SELECT id,title,location,mime_type FROM submission_files
           WHERE id=:file AND submission_id=:submission""",
        {"file": file_id, "submission": submission_id},
    )
    if row is None:
        raise HTTPException(404)
    root = request.app.state.settings.private_storage_root.resolve()
    path = (root / row["location"]).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type=row["mime_type"], filename=row["title"])
