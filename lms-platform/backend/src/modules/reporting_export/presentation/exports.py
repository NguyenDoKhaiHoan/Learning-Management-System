"""Scoped reports, persistent export requests and private authenticated downloads."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_roles
from src.modules.course.presentation.router import Id, Read
from src.modules.reporting_export.application.exports import Exports, public_job
from src.modules.reporting_export.application.reports import CourseReports

router = APIRouter(
    prefix="/api/v1",
    tags=["Reports and exports"],
    responses=ERROR_RESPONSES,
    dependencies=Read + [Depends(require_roles(["ADMIN", "INSTRUCTOR"]))],
)
EnrollmentStatus = Literal["PENDING", "ACTIVE", "SUSPENDED", "COMPLETED"]
GradeStatus = Literal["PUBLISHED", "DRAFT", "ALL"]
AssessmentType = Literal["ASSIGNMENT", "EXAM"]


class ExportFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    search: str = Field(default="", max_length=100)
    enrollment_status: EnrollmentStatus | None = None
    grade_status: GradeStatus = "PUBLISHED"
    assessment_type: AssessmentType | None = None


class ExportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    kind: Literal["OVERVIEW", "LEARNERS", "GRADEBOOK"]
    course_id: int | None = Field(default=None, gt=0, le=18446744073709551615)
    filters: ExportFilters = Field(default_factory=ExportFilters)

    @model_validator(mode="after")
    def course_required(self):
        if (self.kind == "OVERVIEW") != (self.course_id is None):
            raise ValueError("Course is required only for course exports")
        if self.kind == "OVERVIEW" and self.filters != ExportFilters():
            raise ValueError("Overview exports do not accept course filters")
        if self.kind == "LEARNERS" and (
            self.filters.grade_status != "PUBLISHED" or self.filters.assessment_type is not None
        ):
            raise ValueError("Learner exports do not accept grade filters")
        if self.kind == "GRADEBOOK" and self.filters.enrollment_status is not None:
            raise ValueError("Gradebook exports do not accept enrollment status")
        return self


@router.get("/reports/courses/{course_id}/learners", response_model=SuccessResponse[dict])
async def learners(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
    enrollment_status: EnrollmentStatus | None = None,
    search: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    service = CourseReports(connection, actor, request.state.trace_id)
    await service.scope(course_id)
    data = await service.learners(
        course_id, {"enrollment_status": enrollment_status, "search": search}, limit, offset
    )
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.get("/reports/courses/{course_id}/gradebook", response_model=SuccessResponse[dict])
async def gradebook(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
    grade_status: GradeStatus = "PUBLISHED",
    assessment_type: AssessmentType | None = None,
    search: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    service = CourseReports(connection, actor, request.state.trace_id)
    await service.scope(course_id)
    data = await service.gradebook(
        course_id,
        {"grade_status": grade_status, "assessment_type": assessment_type, "search": search},
        limit,
        offset,
    )
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.post("/exports", response_model=SuccessResponse[dict], status_code=202)
async def create_export(
    body: ExportInput,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
):
    data = await Exports(connection, actor, request.state.trace_id).create(body)
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.get("/exports", response_model=SuccessResponse[dict])
async def list_exports(
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    service = Exports(connection, actor, request.state.trace_id)
    params = {"actor": int(actor.id), "limit": limit, "offset": offset}
    count = await service.repo.fetch_one(
        "SELECT COUNT(*) total FROM export_jobs WHERE requested_by=:actor", params
    )
    rows = await service.repo.fetch_all(
        "SELECT * FROM export_jobs WHERE requested_by=:actor ORDER BY created_at DESC,id DESC "
        "LIMIT :limit OFFSET :offset",
        params,
    )
    return SuccessResponse(
        data={
            "items": [public_job(row) for row in rows],
            "total": count["total"],
            "limit": limit,
            "offset": offset,
        },
        trace_id=request.state.trace_id,
    )


@router.get("/exports/{job_id}", response_model=SuccessResponse[dict])
async def export_status(
    job_id: Id, request: Request, connection: ConnectionDependency, actor: CurrentUserDependency
):
    row = await Exports(connection, actor, request.state.trace_id).job(job_id)
    return SuccessResponse(data=public_job(row), trace_id=request.state.trace_id)


@router.get("/exports/{job_id}/content")
async def download_export(
    job_id: Id, request: Request, connection: ConnectionDependency, actor: CurrentUserDependency
):
    service = Exports(connection, actor, request.state.trace_id)
    row = await service.job(job_id)
    if row["status"] != "READY":
        raise HTTPException(409, "Export is not ready")
    root = request.app.state.settings.private_storage_root.resolve()
    path = (root / (row["location"] or "")).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404)
    await service.audit(
        "export.download",
        "export_job",
        job_id,
        details={"kind": row["kind"], "row_count": row["row_count"]},
    )
    await connection.commit()
    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename=f"lms-{row['kind'].lower()}-{job_id}.csv",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
