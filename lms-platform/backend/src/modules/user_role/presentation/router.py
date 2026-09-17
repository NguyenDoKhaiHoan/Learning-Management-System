"""Admin role-assignment endpoints guarded by live database roles."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_roles
from src.modules.audit_security.infrastructure.repository import AuditRepository
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


@router.get("/{user_id}/roles", response_model=SuccessResponse[list[str]])
async def list_user_roles(user_id: UserId, request: Request, connection: ConnectionDependency):
    if await IdentityRepository(connection).get_user(user_id) is None:
        raise HTTPException(404)
    rows = await RoleRepository(connection).fetch_all(
        """SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id=r.id
           WHERE ur.user_id=:id ORDER BY r.code""",
        {"id": user_id},
    )
    return SuccessResponse(data=[row["code"] for row in rows], trace_id=request.state.trace_id)


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
    actor: CurrentUserDependency,
) -> SuccessResponse[dict[str, str]]:
    role = await RoleRepository(connection).get_role(role_code)
    user = await IdentityRepository(connection).get_user(user_id)
    if role is None or user is None:
        await connection.rollback()
        raise HTTPException(404)
    await RoleRepository(connection).assign_role(user_id, int(role["id"]))
    await AuditRepository(connection).append_log(
        actor_id=int(actor.id),
        action="role.assign",
        resource="user",
        resource_id=str(user_id),
        trace_id=request.state.trace_id,
        details={"role": role_code},
    )
    await connection.commit()
    return SuccessResponse(
        data={"user_id": str(user_id), "role": role_code}, trace_id=request.state.trace_id
    )


@router.delete("/{user_id}/roles/{role_code}", response_model=SuccessResponse[dict[str, str]])
async def revoke_role(
    user_id: UserId,
    role_code: RoleCode,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
) -> SuccessResponse[dict[str, str]]:
    role = await RoleRepository(connection).get_role(role_code)
    if role is None or not await RoleRepository(connection).revoke_role(user_id, int(role["id"])):
        await connection.rollback()
        raise HTTPException(404)
    await AuditRepository(connection).append_log(
        actor_id=int(actor.id),
        action="role.revoke",
        resource="user",
        resource_id=str(user_id),
        trace_id=request.state.trace_id,
        details={"role": role_code},
    )
    await connection.commit()
    return SuccessResponse(
        data={"user_id": str(user_id), "role": role_code}, trace_id=request.state.trace_id
    )
