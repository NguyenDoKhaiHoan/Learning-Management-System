"""Admin-only searchable users and account creation/editing."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_roles
from src.modules.course.presentation.router import Id
from src.modules.user_role.application.admin import AdminUsers

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Account administration"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
AccountStatus = Literal["ACTIVE", "INACTIVE", "LOCKED"]


class UserInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.lower()


class UserCreate(UserInput):
    password: SecretStr = Field(min_length=8, max_length=128)
    status: AccountStatus = "ACTIVE"
    roles: list[Literal["ADMIN", "INSTRUCTOR", "STUDENT"]] = Field(
        default_factory=list, max_length=3
    )


class UserOutput(BaseModel):
    id: str
    email: str
    username: str
    status: AccountStatus
    roles: list[str]
    created_at: datetime
    updated_at: datetime


class UserPage(BaseModel):
    items: list[UserOutput]
    total: int
    limit: int
    offset: int


@router.get("", response_model=SuccessResponse[UserPage])
async def list_users(
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
    search: Annotated[str, Query(max_length=254)] = "",
    status: AccountStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    data = await AdminUsers(connection, actor, request.state.trace_id).list(
        search, status, limit, offset
    )
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.post("", status_code=201, response_model=SuccessResponse[UserOutput])
async def create_user(
    body: UserCreate,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
):
    data = await AdminUsers(connection, actor, request.state.trace_id).create(body)
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.put("/{user_id}", response_model=SuccessResponse[UserOutput])
async def update_user(
    user_id: Id,
    body: UserInput,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
):
    data = await AdminUsers(connection, actor, request.state.trace_id).update(user_id, body)
    return SuccessResponse(data=data, trace_id=request.state.trace_id)
