"""Grade items, feedback, publication and version history API."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.course.presentation.router import Id, Publish, Read, Write
from src.modules.gradebook.application.service import GradeService

router = APIRouter(prefix="/api/v1", tags=["Gradebook"], responses=ERROR_RESPONSES)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GradeItem(Input):
    item_key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=16000)
    score: Decimal = Field(ge=0, le=999999.99, max_digits=8, decimal_places=2)
    max_score: Decimal = Field(gt=0, le=999999.99, max_digits=8, decimal_places=2)
    feedback: str | None = Field(default=None, max_length=16000)

    @model_validator(mode="after")
    def valid_score(self):
        if self.score > self.max_score:
            raise ValueError("Score exceeds maximum")
        return self


class GradeContent(Input):
    feedback: str | None = Field(default=None, max_length=16000)
    items: list[GradeItem] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_items(self):
        if len({i.item_key for i in self.items}) != len(self.items):
            raise ValueError("Duplicate item key")
        return self


class CreateGrade(GradeContent):
    enrollment_id: int = Field(gt=0)
    assessment_type: Literal["EXAM", "ASSIGNMENT"]
    assessment_id: int = Field(gt=0)
    source_id: int = Field(gt=0)


class EditGrade(GradeContent):
    expected_version: int = Field(ge=1)


class ReviseGrade(EditGrade):
    reason: str = Field(min_length=1, max_length=4000)


class PublishGrade(Input):
    expected_version: int = Field(ge=1)


def service(connection, user, request):
    return GradeService(connection, user, request.state.trace_id)


def result(request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.post(
    "/courses/{course_id}/grades",
    dependencies=Write,
    status_code=201,
    response_model=SuccessResponse[dict],
)
async def create_grade(
    course_id: Id,
    body: CreateGrade,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    return result(request, await service(connection, user, request).create(course_id, body))


@router.get(
    "/courses/{course_id}/grades", dependencies=Write, response_model=SuccessResponse[list[dict]]
)
async def list_grades(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    return result(request, await service(connection, user, request).list(course_id))


@router.get(
    "/courses/{course_id}/grades/me", dependencies=Read, response_model=SuccessResponse[list[dict]]
)
async def my_grades(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    return result(request, await service(connection, user, request).list(course_id, student=True))


@router.get("/grades/{grade_id}", dependencies=Write, response_model=SuccessResponse[dict])
async def get_grade(
    grade_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    s = service(connection, user, request)
    await s.locked(grade_id)
    return result(request, await s.grades.detail(grade_id))


@router.put("/grades/{grade_id}", dependencies=Write, response_model=SuccessResponse[dict])
async def edit_grade(
    grade_id: Id,
    body: EditGrade,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    return result(request, await service(connection, user, request).edit(grade_id, body))


@router.post(
    "/grades/{grade_id}/publish", dependencies=Publish, response_model=SuccessResponse[dict]
)
async def publish_grade(
    grade_id: Id,
    body: PublishGrade,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    return result(request, await service(connection, user, request).publish(grade_id, body))


@router.post("/grades/{grade_id}/revise", dependencies=Write, response_model=SuccessResponse[dict])
async def revise_grade(
    grade_id: Id,
    body: ReviseGrade,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    data = await service(connection, user, request).edit(grade_id, body, revise=True)
    return result(request, data)


@router.get(
    "/grades/{grade_id}/history", dependencies=Write, response_model=SuccessResponse[list[dict]]
)
async def grade_history(
    grade_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    return result(request, await service(connection, user, request).history(grade_id))
