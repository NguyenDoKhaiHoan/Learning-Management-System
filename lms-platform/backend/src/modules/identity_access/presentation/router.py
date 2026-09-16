"""Authentication and account-administration HTTP endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field, field_validator

from src.core.contracts import ERROR_RESPONSES, AccessToken, CurrentUser, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_roles
from src.core.security.jwt import create_access_token
from src.modules.identity_access.application.passwords import verify_password
from src.modules.identity_access.domain.enums import UserStatus
from src.modules.identity_access.infrastructure.repository import IdentityRepository

router = APIRouter(prefix="/api/v1/auth", tags=["Identity"], responses=ERROR_RESPONSES)
DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$600000$FXFSYYgo5ZlR0VIg82NLHw=="
    "$i2g9c4YxXOs2HQuRnh6XTE4K747dA9tnhEdqiQZJyUg="
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


@router.post("/login", response_model=SuccessResponse[AccessToken])
async def login(
    body: LoginRequest, request: Request, connection: ConnectionDependency
) -> SuccessResponse[AccessToken]:
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
    token = create_access_token(int(credentials["id"]), settings)
    return SuccessResponse(
        data=AccessToken(
            access_token=token,
            expires_in=settings.access_token_expire_minutes * 60,
        ),
        trace_id=request.state.trace_id,
    )


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
) -> SuccessResponse[dict[str, str]]:
    updated = await IdentityRepository(connection).set_status(user_id, UserStatus(body.status))
    if not updated:
        await connection.rollback()
        raise HTTPException(404)
    await connection.commit()
    return SuccessResponse(
        data={"user_id": str(user_id), "status": body.status},
        trace_id=request.state.trace_id,
    )
