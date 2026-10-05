"""Portal report APIs with live backend role and permission enforcement."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_roles
from src.modules.course.presentation.router import Read
from src.modules.reporting_export.application.service import DashboardReports

router = APIRouter(prefix="/api/v1", tags=["Dashboards"], responses=ERROR_RESPONSES)


class CourseReport(BaseModel):
    id: str
    code: str
    title: str
    status: str
    enrollments: int
    active_enrollments: int
    completed_learners: int
    draft_grades: int
    submissions: int


class DashboardOutput(BaseModel):
    totals: dict[str, int]
    courses: list[CourseReport]
    total_courses: int
    limit: int
    offset: int


@router.get(
    "/reports/overview",
    dependencies=[Depends(require_roles(["ADMIN"]))],
    response_model=SuccessResponse[DashboardOutput],
)
async def overview(
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    data = await DashboardReports(connection).overview(actor)
    courses = data["courses"]
    for course in courses:
        course["id"] = str(course["id"])
    data.update(
        total_courses=len(courses),
        courses=courses[offset : offset + limit],
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.get(
    "/dashboard/instructor",
    dependencies=Read + [Depends(require_roles(["INSTRUCTOR"]))],
    response_model=SuccessResponse[DashboardOutput],
)
async def instructor(
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    courses = await DashboardReports(connection).courses(actor)
    totals = {
        "total_courses": len(courses),
        "active_enrollments": sum(c["active_enrollments"] for c in courses),
        "draft_grades": sum(c["draft_grades"] for c in courses),
        "submissions": sum(c["submissions"] for c in courses),
    }
    for course in courses:
        course["id"] = str(course["id"])
    data = {
        "totals": totals,
        "total_courses": len(courses),
        "courses": courses[offset : offset + limit],
        "limit": limit,
        "offset": offset,
    }
    return SuccessResponse(data=data, trace_id=request.state.trace_id)
