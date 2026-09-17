"""Manage current grants for the application's supported permission catalog."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency, require_roles
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.user_role.infrastructure.repository import RoleRepository

router = APIRouter(
    prefix="/api/v1",
    tags=["Permissions"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_roles(["ADMIN"]))],
)
Permission = Literal["course.read", "course.write", "course.publish"]
RoleCode = Annotated[str, Path(pattern=r"^[A-Z][A-Z0-9_]{1,31}$")]


@router.get("/permissions", response_model=SuccessResponse[list[str]])
async def catalog(request: Request):
    return SuccessResponse(
        data=["course.read", "course.write", "course.publish"], trace_id=request.state.trace_id
    )


@router.get("/roles", response_model=SuccessResponse[list[dict[str, str]]])
async def roles(request: Request, connection: ConnectionDependency):
    rows = await RoleRepository(connection).fetch_all("SELECT code, name FROM roles ORDER BY code")
    return SuccessResponse(data=rows, trace_id=request.state.trace_id)


@router.get("/roles/{role_code}/permissions", response_model=SuccessResponse[list[str]])
async def grants(role_code: RoleCode, request: Request, connection: ConnectionDependency):
    repo = RoleRepository(connection)
    if not await repo.get_role(role_code):
        raise HTTPException(404)
    rows = await repo.fetch_all(
        """SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id
           JOIN roles r ON r.id=rp.role_id WHERE r.code=:code ORDER BY p.code""",
        {"code": role_code},
    )
    return SuccessResponse(data=[row["code"] for row in rows], trace_id=request.state.trace_id)


@router.put(
    "/roles/{role_code}/permissions/{permission}", response_model=SuccessResponse[dict[str, str]]
)
@router.delete(
    "/roles/{role_code}/permissions/{permission}", response_model=SuccessResponse[dict[str, str]]
)
async def change_grant(
    role_code: RoleCode,
    permission: Permission,
    request: Request,
    connection: ConnectionDependency,
    actor: CurrentUserDependency,
):
    repo = RoleRepository(connection)
    role = await repo.get_role(role_code)
    if role is None:
        raise HTTPException(404)
    if request.method == "PUT":
        await repo.execute(
            "INSERT IGNORE INTO permissions (code) VALUES (:code)", {"code": permission}
        )
        await repo.execute(
            """INSERT IGNORE INTO role_permissions (role_id, permission_id)
               SELECT :role, id FROM permissions WHERE code=:code""",
            {"role": role["id"], "code": permission},
        )
    else:
        await repo.execute(
            """DELETE rp FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id
               WHERE rp.role_id=:role AND p.code=:code""",
            {"role": role["id"], "code": permission},
        )
    await AuditRepository(connection).append_log(
        actor_id=int(actor.id),
        action="permission.grant" if request.method == "PUT" else "permission.revoke",
        resource="role",
        resource_id=str(role["id"]),
        trace_id=request.state.trace_id,
        details={"permission": permission},
    )
    await connection.commit()
    return SuccessResponse(
        data={"role": role_code, "permission": permission}, trace_id=request.state.trace_id
    )
