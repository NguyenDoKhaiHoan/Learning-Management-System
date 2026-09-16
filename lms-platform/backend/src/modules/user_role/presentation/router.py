"""Admin role-assignment endpoints guarded by live database roles."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import require_roles
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.user_role.infrastructure.repository import RoleRepository

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Roles"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_roles(["ADMIN"]))],
)

UserId = Annotated[int, Path(gt=0)]
RoleCode = Annotated[str, Path(pattern=r"^[A-Z][A-Z0-9_]{1,31}$")]


@router.put(
    "/{user_id}/roles/{role_code}",
    response_model=SuccessResponse[dict[str, str]],
    status_code=status.HTTP_201_CREATED,
)
async def assign_role(
    user_id: UserId,
    role_code: RoleCode,
    request: Request,
    connection: ConnectionDependency,
) -> SuccessResponse[dict[str, str]]:
    role = await RoleRepository(connection).get_role(role_code)
    user = await IdentityRepository(connection).get_user(user_id)
    if role is None or user is None:
        await connection.rollback()
        raise HTTPException(404)
    await RoleRepository(connection).assign_role(user_id, int(role["id"]))
    await connection.commit()
    return SuccessResponse(
        data={"user_id": str(user_id), "role": role_code}, trace_id=request.state.trace_id
    )


@router.delete(
    "/{user_id}/roles/{role_code}", response_model=SuccessResponse[dict[str, str]]
)
async def revoke_role(
    user_id: UserId,
    role_code: RoleCode,
    request: Request,
    connection: ConnectionDependency,
) -> SuccessResponse[dict[str, str]]:
    role = await RoleRepository(connection).get_role(role_code)
    if role is None or not await RoleRepository(connection).revoke_role(user_id, int(role["id"])):
        await connection.rollback()
        raise HTTPException(404)
    await connection.commit()
    return SuccessResponse(
        data={"user_id": str(user_id), "role": role_code}, trace_id=request.state.trace_id
    )
