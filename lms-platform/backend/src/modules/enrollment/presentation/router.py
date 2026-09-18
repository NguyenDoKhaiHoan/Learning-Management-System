"""Published catalog, enrollment requests/approval and course staff APIs."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_roles
from src.modules.course.presentation.router import Id, Read, Write
from src.modules.enrollment.application.service import EnrollmentService
from src.modules.enrollment.domain.enums import CourseStaffRole, EnrollmentStatus
from src.modules.enrollment.infrastructure.repository import EnrollmentRepository
from src.modules.user_role.infrastructure.repository import RoleRepository

router = APIRouter(prefix="/api/v1", tags=["Enrollments"], responses=ERROR_RESPONSES)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
ManagerRead = [Depends(require_roles(["ADMIN", "INSTRUCTOR"])), *Read]
AdminWrite = [Depends(require_roles(["ADMIN"])), *Write]


class EnrollmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: int | None = Field(default=None, gt=0, le=18446744073709551615)


class EnrollmentOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    id: str
    student_id: str
    course_id: str
    status: EnrollmentStatus
    completed_at: datetime | None


class MyEnrollment(EnrollmentOutput):
    title: str
    course_status: str


class EnrollmentStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ACTIVE", "SUSPENDED"]


class StaffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: CourseStaffRole


class StaffOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    user_id: str
    username: str
    role: CourseStaffRole


class CatalogCourse(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    id: str
    code: str
    title: str
    description: str | None


@router.get(
    "/catalog/courses", dependencies=Read, response_model=SuccessResponse[list[CatalogCourse]]
)
async def catalog(
    request: Request, connection: ConnectionDependency, limit: Limit = 20, offset: Offset = 0
):
    rows = await EnrollmentRepository(connection).fetch_all(
        """SELECT id,code,title,description FROM courses
           WHERE status='PUBLISHED' AND deleted_at IS NULL ORDER BY id DESC
           LIMIT :limit OFFSET :offset""",
        {"limit": limit, "offset": offset},
    )
    return SuccessResponse(data=rows, trace_id=request.state.trace_id)


@router.get(
    "/enrollments/me", dependencies=Read, response_model=SuccessResponse[list[MyEnrollment]]
)
async def my_enrollments(
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    limit: Limit = 20,
    offset: Offset = 0,
):
    rows = await EnrollmentRepository(connection).fetch_all(
        """SELECT e.id,e.student_id,e.course_id,e.status,e.completed_at,
                  c.title,c.status course_status
           FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.student_id=:id
           AND c.deleted_at IS NULL ORDER BY e.id DESC LIMIT :limit OFFSET :offset""",
        {"id": int(user.id), "limit": limit, "offset": offset},
    )
    return SuccessResponse(data=rows, trace_id=request.state.trace_id)


@router.post(
    "/courses/{course_id}/enrollments",
    status_code=201,
    response_model=SuccessResponse[EnrollmentOutput],
)
async def enroll(
    course_id: Id,
    body: EnrollmentInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    student_id = body.student_id if body.student_id is not None else int(user.id)
    self_enrollment = student_id == int(user.id) and "STUDENT" in user.roles
    permissions = await RoleRepository(connection).get_permission_codes(int(user.id))
    if self_enrollment:
        if "course.read" not in permissions:
            raise HTTPException(403)
    elif not {"ADMIN", "INSTRUCTOR"}.intersection(user.roles) or "course.write" not in permissions:
        raise HTTPException(403)
    row = await EnrollmentService(connection, user, request.state.trace_id).enroll(
        course_id, student_id, self_enrollment=self_enrollment
    )
    return SuccessResponse(data=row, trace_id=request.state.trace_id)


@router.get(
    "/courses/{course_id}/enrollments",
    dependencies=ManagerRead,
    response_model=SuccessResponse[list[EnrollmentOutput]],
)
async def list_enrollments(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    limit: Limit = 20,
    offset: Offset = 0,
):
    service = EnrollmentService(connection, user, request.state.trace_id)
    # write=True requires manager scope; being an enrolled Instructor is insufficient.
    await service.authorize(course_id, write=True)
    rows = await service.repo.fetch_all(
        """SELECT e.id,e.student_id,e.course_id,e.status,e.completed_at FROM enrollments e
           JOIN users u ON u.id=e.student_id WHERE e.course_id=:id AND u.deleted_at IS NULL
           ORDER BY e.id DESC LIMIT :limit OFFSET :offset""",
        {"id": course_id, "limit": limit, "offset": offset},
    )
    return SuccessResponse(data=rows, trace_id=request.state.trace_id)


@router.patch(
    "/courses/{course_id}/enrollments/{student_id}",
    dependencies=Write,
    response_model=SuccessResponse[EnrollmentOutput],
)
async def enrollment_status(
    course_id: Id,
    student_id: Id,
    body: EnrollmentStatusInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    row = await EnrollmentService(connection, user, request.state.trace_id).set_status(
        course_id, student_id, body.status
    )
    return SuccessResponse(data=row, trace_id=request.state.trace_id)


@router.get(
    "/courses/{course_id}/staff",
    dependencies=ManagerRead,
    response_model=SuccessResponse[list[StaffOutput]],
)
async def list_staff(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    service = EnrollmentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True)
    rows = await service.repo.fetch_all(
        """SELECT s.user_id,u.username,s.role FROM course_staff s JOIN users u ON u.id=s.user_id
           WHERE s.course_id=:id AND u.deleted_at IS NULL ORDER BY s.id""",
        {"id": course_id},
    )
    return SuccessResponse(data=rows, trace_id=request.state.trace_id)


@router.put(
    "/courses/{course_id}/staff/{user_id}",
    dependencies=AdminWrite,
    response_model=SuccessResponse[dict[str, str]],
)
async def assign_staff(
    course_id: Id,
    user_id: Id,
    body: StaffInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    await EnrollmentService(connection, user, request.state.trace_id).set_staff(
        course_id, user_id, body.role
    )
    return SuccessResponse(
        data={"user_id": str(user_id), "role": body.role}, trace_id=request.state.trace_id
    )


@router.delete(
    "/courses/{course_id}/staff/{user_id}",
    dependencies=AdminWrite,
    response_model=SuccessResponse[dict[str, str]],
)
async def remove_staff(
    course_id: Id,
    user_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    await EnrollmentService(connection, user, request.state.trace_id).set_staff(
        course_id, user_id, None
    )
    return SuccessResponse(data={"user_id": str(user_id)}, trace_id=request.state.trace_id)
