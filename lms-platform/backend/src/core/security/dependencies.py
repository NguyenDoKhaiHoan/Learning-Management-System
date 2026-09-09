"""JWT authentication and global role checks backed by current SQL data."""

from collections.abc import Callable, Sequence
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.contracts import CurrentUser
from src.core.database.database import ConnectionDependency
from src.core.security.jwt import decode_access_token
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.user_role.infrastructure.repository import RoleRepository

bearer = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_token_subject(request: Request, credentials: BearerCredentials) -> int:
    """Reject missing/invalid tokens before acquiring a database connection."""
    unauthorized = HTTPException(401, headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    try:
        return decode_access_token(credentials.credentials, request.app.state.settings)
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise unauthorized from None


async def get_current_user(
    user_id: Annotated[int, Depends(get_token_subject)],
    connection: ConnectionDependency,
) -> CurrentUser:
    unauthorized = HTTPException(401, headers={"WWW-Authenticate": "Bearer"})
    user = await IdentityRepository(connection).get_user(user_id)
    if user is None or user["status"] != "ACTIVE":
        raise unauthorized
    roles = await RoleRepository(connection).get_role_codes(user_id)
    return CurrentUser(
        id=str(user["id"]), email=user["email"], username=user["username"], roles=tuple(roles)
    )


CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user)]


def require_roles(allowed_roles: Sequence[str]) -> Callable[..., CurrentUser]:
    """Allow any requested global role; resource ownership remains a use-case rule."""
    allowed = frozenset(allowed_roles)
    if not allowed or isinstance(allowed_roles, str):
        raise ValueError("Provide a non-empty list of role codes")

    def check(user: CurrentUserDependency) -> CurrentUser:
        if allowed.isdisjoint(user.roles):
            raise HTTPException(403)
        return user

    return check
