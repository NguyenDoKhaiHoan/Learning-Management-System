"""Course CRUD with live permission checks and ownership/enrollment scope."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_permissions, require_roles
from src.modules.course.application.service import CourseService
from src.modules.course.domain.enums import CourseStatus
from src.modules.course.infrastructure.repository import CourseRepository

router = APIRouter(prefix="/api/v1/courses", tags=["Courses"], responses=ERROR_RESPONSES)
Id = Annotated[int, Path(gt=0, le=18446744073709551615)]
Read = [Depends(require_permissions(["course.read"]))]
Write = [
    Depends(require_roles(["ADMIN", "INSTRUCTOR"])),
    Depends(require_permissions(["course.write"])),
]
Publish = [
    Depends(require_roles(["ADMIN", "INSTRUCTOR"])),
    Depends(require_permissions(["course.publish"])),
]


class CourseInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=16000)


class CourseOutput(CourseInput):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    id: str
    created_by: str
    status: CourseStatus
    created_at: datetime
    updated_at: datetime


class TransitionInput(BaseModel):
    status: CourseStatus


@router.post("", dependencies=Write, status_code=201, response_model=SuccessResponse[CourseOutput])
async def create_course(
    body: CourseInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = CourseService(connection, user, request.state.trace_id)
    course_id = await service.repo.create(**body.model_dump(), created_by=int(user.id))
    await service.audit("course.create", "course", course_id)
    await connection.commit()
    return SuccessResponse(data=await service.repo.get(course_id), trace_id=request.state.trace_id)


@router.get("", dependencies=Read, response_model=SuccessResponse[list[CourseOutput]])
async def list_courses(
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: CourseStatus | None = None,
):
    rows = await CourseRepository(connection).fetch_all(
        """SELECT c.id, c.code, c.title, c.description, c.created_by, c.status,
                  c.created_at, c.updated_at FROM courses c
           WHERE c.deleted_at IS NULL AND (:status IS NULL OR c.status=:status)
           AND (:admin=1 OR (:instructor=1 AND (c.created_by=:user OR EXISTS
             (SELECT 1 FROM course_staff s WHERE s.course_id=c.id AND s.user_id=:user
              AND s.role='INSTRUCTOR'))) OR (c.status='PUBLISHED' AND EXISTS
             (SELECT 1 FROM enrollments e WHERE e.course_id=c.id AND e.student_id=:user
              AND e.status='ACTIVE')))
           ORDER BY c.id DESC LIMIT :limit OFFSET :offset""",
        {
            "status": status,
            "admin": "ADMIN" in user.roles,
            "instructor": "INSTRUCTOR" in user.roles,
            "user": int(user.id),
            "limit": limit,
            "offset": offset,
        },
    )
    return SuccessResponse(data=rows, trace_id=request.state.trace_id)


@router.get("/{course_id}", dependencies=Read, response_model=SuccessResponse[CourseOutput])
async def get_course(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    row = await CourseService(connection, user, request.state.trace_id).authorize(course_id)
    return SuccessResponse(data=row, trace_id=request.state.trace_id)


@router.put("/{course_id}", dependencies=Write, response_model=SuccessResponse[CourseOutput])
async def update_course(
    course_id: Id,
    body: CourseInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = CourseService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.repo.execute(
        "UPDATE courses SET code=:code, title=:title, description=:description WHERE id=:id",
        {**body.model_dump(), "id": course_id},
    )
    await service.audit("course.update", "course", course_id)
    await connection.commit()
    return SuccessResponse(data=await service.repo.get(course_id), trace_id=request.state.trace_id)


@router.delete("/{course_id}", dependencies=Write, response_model=SuccessResponse[dict[str, str]])
async def delete_course(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    service = CourseService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.repo.soft_delete(course_id)
    await service.audit("course.delete", "course", course_id)
    await connection.commit()
    return SuccessResponse(data={"id": str(course_id)}, trace_id=request.state.trace_id)


@router.post(
    "/{course_id}/status", dependencies=Publish, response_model=SuccessResponse[CourseOutput]
)
async def transition_course(
    course_id: Id,
    body: TransitionInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    row = await CourseService(connection, user, request.state.trace_id).transition(
        course_id, body.status
    )
    return SuccessResponse(data=row, trace_id=request.state.trace_id)
