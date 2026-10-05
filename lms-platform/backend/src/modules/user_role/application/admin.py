"""Public account projections and audited administration; never serialize credentials."""

from fastapi import HTTPException

from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.identity_access.application.passwords import hash_password
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.user_role.infrastructure.repository import RoleRepository


class AdminUsers:
    def __init__(self, connection, actor, trace_id):
        self.connection = connection
        self.actor = actor
        self.trace_id = trace_id
        self.repo = IdentityRepository(connection)

    async def detail(self, id):
        user = await self.repo.get_user(id)
        if not user:
            raise HTTPException(404)
        roles = await self.repo.fetch_all(
            """SELECT r.code FROM roles r JOIN user_roles ur ON ur.role_id=r.id
            WHERE ur.user_id=:id ORDER BY r.code""",
            {"id": id},
        )
        return user | {"id": str(user["id"]), "roles": [r["code"] for r in roles]}

    async def list(self, search, status, limit, offset):
        params = {"search": "%" + search + "%", "status": status, "limit": limit, "offset": offset}
        where = """WHERE deleted_at IS NULL AND (username LIKE :search OR email LIKE :search)
            AND (:status IS NULL OR status=:status)"""
        total = await self.repo.fetch_one("SELECT COUNT(*) AS count FROM users " + where, params)
        rows = await self.repo.fetch_all(
            "SELECT id FROM users " + where + " ORDER BY id LIMIT :limit OFFSET :offset", params
        )
        return {
            "items": [await self.detail(r["id"]) for r in rows],
            "total": total["count"],
            "limit": limit,
            "offset": offset,
        }

    async def create(self, body):
        roles = RoleRepository(self.connection)
        ids = []
        for code in body.roles:
            role = await roles.get_role(code)
            if not role:
                raise HTTPException(422, "Unknown role")
            ids.append(role["id"])
        id = await self.repo.create_user(
            email=body.email,
            username=body.username,
            hashed_password=hash_password(body.password.get_secret_value()),
            status=body.status,
        )
        for role_id in ids:
            await roles.assign_role(id, role_id)
        await self.audit("account.create", id)
        await self.connection.commit()
        return await self.detail(id)

    async def update(self, id, body):
        row = await self.repo.fetch_one(
            "SELECT id FROM users WHERE id=:id AND deleted_at IS NULL FOR UPDATE", {"id": id}
        )
        if not row:
            raise HTTPException(404)
        await self.repo.execute(
            "UPDATE users SET email=:email,username=:username WHERE id=:id",
            {"id": id, "email": body.email, "username": body.username},
        )
        await self.audit("account.update", id)
        await self.connection.commit()
        return await self.detail(id)

    async def audit(self, action, id):
        await AuditRepository(self.connection).append_log(
            actor_id=int(self.actor.id),
            action=action,
            resource="user",
            resource_id=str(id),
            trace_id=self.trace_id,
        )
