"""Student event ingestion and scoped Instructor/Admin human review."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.anti_cheating.application.service import AttemptEvents
from src.modules.course.presentation.router import Id, Read, Write

router = APIRouter(prefix="/api/v1", tags=["Attempt events"], responses=ERROR_RESPONSES)


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_event_id: UUID
    event_type: Literal["TAB_HIDDEN", "WINDOW_BLUR"]


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    status: Literal["REVIEWED", "DISMISSED"]
    note: str = Field(min_length=1, max_length=1000)


@router.post(
    "/attempts/{attempt_id}/events",
    dependencies=Read,
    response_model=SuccessResponse[dict],
    status_code=201,
)
async def record_event(
    attempt_id: Id,
    body: EventInput,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
):
    data = await AttemptEvents(connection, actor, request.state.trace_id).record(attempt_id, body)
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.get(
    "/courses/{course_id}/attempt-events", dependencies=Write, response_model=SuccessResponse[dict]
)
async def list_events(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
    status: Literal["PENDING", "REVIEWED", "DISMISSED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    data = await AttemptEvents(connection, actor, request.state.trace_id).list(
        course_id,
        status,
        limit,
        offset,
    )
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.patch(
    "/courses/{course_id}/attempt-events/{event_id}/review",
    dependencies=Write,
    response_model=SuccessResponse[dict],
)
async def review_event(
    course_id: Id,
    event_id: Id,
    body: ReviewInput,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
):
    data = await AttemptEvents(connection, actor, request.state.trace_id).review(
        course_id, event_id, body
    )
    return SuccessResponse(data=data, trace_id=request.state.trace_id)
