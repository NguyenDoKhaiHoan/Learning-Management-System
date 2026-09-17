"""Authentication and account-administration HTTP endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel, Field, field_validator

from src.core.contracts import ERROR_RESPONSES, AccessToken, CurrentUser, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_roles
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.identity_access.application.passwords import verify_password
from src.modules.identity_access.application.sessions import consume_refresh, issue_tokens
from src.modules.identity_access.domain.enums import UserStatus
from src.modules.identity_access.infrastructure.repository import IdentityRepository

router = APIRouter(prefix="/api/v1/auth", tags=["Identity"], responses=ERROR_RESPONSES)
DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$600000$FXFSYYgo5ZlR0VIg82NLHw==$i2g9c4YxXOs2HQuRnh6XTE4K747dA9tnhEdqiQZJyUg="
)


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        value = value.strip()
        return value.lower() if "@" in value else value


class AccountStatusRequest(BaseModel):
    status: Literal["ACTIVE", "INACTIVE", "LOCKED"]


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


@router.post("/login", response_model=SuccessResponse[AccessToken])
async def login(
    body: LoginRequest, request: Request, response: Response, connection: ConnectionDependency
) -> SuccessResponse[AccessToken]:
    response.headers["Cache-Control"] = "no-store"
    credentials = await IdentityRepository(connection).get_credentials_by_login(body.login)
    password_valid = verify_password(
        body.password,
        credentials["hashed_password"] if credentials is not None else DUMMY_PASSWORD_HASH,
    )
    if (
        credentials is None
        or credentials["status"] != UserStatus.ACTIVE.value
        or not password_valid
    ):
        raise HTTPException(401, headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.settings
    tokens = await issue_tokens(connection, settings, int(credentials["id"]))
    await connection.commit()
    return SuccessResponse(
        data=tokens,
        trace_id=request.state.trace_id,
    )


@router.post("/refresh", response_model=SuccessResponse[AccessToken])
async def refresh(
    body: RefreshRequest, request: Request, response: Response, connection: ConnectionDependency
):
    response.headers["Cache-Control"] = "no-store"
    tokens = await consume_refresh(
        connection, request.app.state.settings, body.refresh_token, request.state.trace_id
    )
    return SuccessResponse(data=tokens, trace_id=request.state.trace_id)


@router.post("/logout", response_model=SuccessResponse[dict[str, bool]])
async def logout(body: RefreshRequest, request: Request, connection: ConnectionDependency):
    await consume_refresh(
        connection,
        request.app.state.settings,
        body.refresh_token,
        request.state.trace_id,
        logout=True,
    )
    return SuccessResponse(data={"logged_out": True}, trace_id=request.state.trace_id)


@router.get("/me", response_model=SuccessResponse[CurrentUser])
async def me(request: Request, user: CurrentUserDependency) -> SuccessResponse[CurrentUser]:
    return SuccessResponse(data=user, trace_id=request.state.trace_id)


@router.patch(
    "/users/{user_id}/status",
    response_model=SuccessResponse[dict[str, str]],
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
async def update_account_status(
    user_id: Annotated[int, Path(gt=0)],
    body: AccountStatusRequest,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
) -> SuccessResponse[dict[str, str]]:
    updated = await IdentityRepository(connection).set_status(user_id, UserStatus(body.status))
    if not updated:
        await connection.rollback()
        raise HTTPException(404)
    if body.status != "ACTIVE":
        await IdentityRepository(connection).execute(
            """UPDATE refresh_tokens SET revoked_at = UTC_TIMESTAMP(6)
               WHERE user_id = :id AND revoked_at IS NULL""",
            {"id": user_id},
        )
    await AuditRepository(connection).append_log(
        actor_id=int(actor.id),
        action="account.status",
        resource="user",
        resource_id=str(user_id),
        trace_id=request.state.trace_id,
        details={"status": body.status},
    )
    await connection.commit()
    return SuccessResponse(
        data={"user_id": str(user_id), "status": body.status},
        trace_id=request.state.trace_id,
    )
