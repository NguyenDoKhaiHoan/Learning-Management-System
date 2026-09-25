"""Completion-rule management and current learner progress APIs."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.course.application.service import CourseService
from src.modules.course.presentation.router import Id, Read, Write
from src.modules.learning_progress_analytics.application.service import ProgressService
from src.modules.learning_progress_analytics.domain.enums import LessonProgressStatus
from src.modules.learning_progress_analytics.infrastructure.repository import ProgressRepository

router = APIRouter(
    prefix="/api/v1/courses/{course_id}",
    tags=["Learning progress"],
    responses=ERROR_RESPONSES,
)


class CompletionRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_lesson_percent: float = Field(gt=0, le=100)
    require_submitted_assignments: bool = False


class CompletionRuleOutput(CompletionRuleInput):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    course_id: str
    updated_by: str | None = None
    updated_at: datetime | None = None


class LessonProgressInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: LessonProgressStatus
    last_position_seconds: int = Field(default=0, ge=0, le=4294967295)


class LessonProgressOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    enrollment_id: str
    lesson_id: str
    status: LessonProgressStatus
    last_position_seconds: int
    started_at: datetime
    completed_at: datetime | None = None
    updated_at: datetime


class CourseProgressOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    enrollment_id: str
    completed_lessons: int
    total_lessons: int
    completed_assignments: int
    total_assignments: int
    progress_percent: float
    completed_at: datetime | None = None
    updated_at: datetime | None = None


class ProgressUpdateOutput(BaseModel):
    lesson: LessonProgressOutput
    course: CourseProgressOutput


def result(request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.get(
    "/completion-rule", dependencies=Read, response_model=SuccessResponse[CompletionRuleOutput]
)
async def get_completion_rule(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    await CourseService(connection, user, request.state.trace_id).authorize(course_id)
    row = await ProgressRepository(connection).completion_rule(course_id)
    return result(
        request,
        row
        or {
            "course_id": str(course_id),
            "required_lesson_percent": 100,
            "require_submitted_assignments": False,
            "updated_by": None,
            "updated_at": None,
        },
    )


@router.put(
    "/completion-rule", dependencies=Write, response_model=SuccessResponse[CompletionRuleOutput]
)
async def put_completion_rule(
    course_id: Id,
    body: CompletionRuleInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = CourseService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    repo = ProgressRepository(connection)
    await repo.execute(
        """INSERT INTO completion_rules
           (course_id, required_lesson_percent, require_submitted_assignments, updated_by)
           VALUES (:course, :percent, :assignments, :user)
           ON DUPLICATE KEY UPDATE required_lesson_percent=VALUES(required_lesson_percent),
             require_submitted_assignments=VALUES(require_submitted_assignments),
             updated_by=VALUES(updated_by)""",
        {
            "course": course_id,
            "percent": body.required_lesson_percent,
            "assignments": body.require_submitted_assignments,
            "user": int(user.id),
        },
    )
    await service.audit("completion_rule.update", "course", course_id)
    await connection.commit()
    return result(request, await repo.completion_rule(course_id))


@router.get("/progress/me", dependencies=Read, response_model=SuccessResponse[CourseProgressOutput])
async def my_course_progress(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ProgressService(connection, user, request.state.trace_id)
    enrollment = await service.learner_context(course_id, lock=True)
    # A course may have been returned to Draft, edited and republished.
    row = await service.refresh_course(course_id, enrollment["id"])
    await connection.commit()
    return result(request, row)


@router.put(
    "/lessons/{lesson_id}/progress",
    dependencies=Read,
    response_model=SuccessResponse[ProgressUpdateOutput],
)
async def update_lesson_progress(
    course_id: Id,
    lesson_id: Id,
    body: LessonProgressInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    if body.status == LessonProgressStatus.NOT_STARTED:
        raise HTTPException(409, "Lesson progress cannot move backwards")
    lesson, course = await ProgressService(connection, user, request.state.trace_id).update_lesson(
        course_id, lesson_id, body.status, body.last_position_seconds
    )
    return result(request, {"lesson": lesson, "course": course})
