"""Global RBAC SQL. Mutations require authorization in the calling use case."""

from src.core.database.sql import SqlRepository


class RoleRepository(SqlRepository):
    async def create_role(self, code: str, name: str) -> int:
        return await self.insert(
            "INSERT INTO roles (code, name) VALUES (:code, :name)", {"code": code, "name": name}
        )

    async def create_permission(self, code: str, description: str | None = None) -> int:
        return await self.insert(
            "INSERT INTO permissions (code, description) VALUES (:code, :description)",
            {"code": code, "description": description},
        )

    async def assign_role(self, user_id: int, role_id: int) -> int:
        return await self.insert(
            "INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)",
            {"user_id": user_id, "role_id": role_id},
        )

    async def grant_permission(self, role_id: int, permission_id: int) -> int:
        return await self.insert(
            """INSERT INTO role_permissions (role_id, permission_id)
               VALUES (:role_id, :permission_id)""",
            {"role_id": role_id, "permission_id": permission_id},
        )

    async def get_role_codes(self, user_id: int) -> list[str]:
        rows = await self.fetch_all(
            """SELECT r.code FROM roles r
               JOIN user_roles ur ON ur.role_id = r.id
               JOIN users u ON u.id = ur.user_id
               WHERE u.id = :user_id AND u.deleted_at IS NULL AND u.status = 'ACTIVE'
               ORDER BY r.code""",
            {"user_id": user_id},
        )
        return [row["code"] for row in rows]

    async def get_permission_codes(self, user_id: int) -> list[str]:
        rows = await self.fetch_all(
            """SELECT DISTINCT p.code FROM permissions p
               JOIN role_permissions rp ON rp.permission_id = p.id
               JOIN user_roles ur ON ur.role_id = rp.role_id
               JOIN users u ON u.id = ur.user_id
               WHERE u.id = :user_id AND u.deleted_at IS NULL AND u.status = 'ACTIVE'
               ORDER BY p.code""",
            {"user_id": user_id},
        )
        return [row["code"] for row in rows]
