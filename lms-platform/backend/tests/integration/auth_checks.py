"""Exercise HTTP JWT/RBAC against current rows in a disposable MySQL database."""

from typing import Annotated

from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.config import Settings
from src.core.security.dependencies import require_roles
from src.core.security.jwt import create_access_token
from src.main import create_app
from src.modules.identity_access.domain.enums import UserStatus
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.user_role.infrastructure.repository import RoleRepository


async def assert_http_auth(engine: AsyncEngine) -> None:
    config = Settings(
        _env_file=None,
        app_env="test",
        db_host_override=None,
        database_url=engine.url.render_as_string(hide_password=False),
        jwt_secret="integration-auth-secret-" * 3,
    )
    async with engine.begin() as connection:
        user = await IdentityRepository(connection).create_user(
            email="auth@example.com",
            username="auth",
            hashed_password="test-only-hash",
            status=UserStatus.ACTIVE,
        )
        role = await RoleRepository(connection).create_role("ADMIN", "Administrator")
        await RoleRepository(connection).assign_role(user, role)
    app = create_app(config)

    @app.get("/test/staff")
    def staff(current: Annotated[object, Depends(require_roles(["ADMIN", "INSTRUCTOR"]))]):
        return {"ok": True}

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = create_access_token(user, config)
            headers = {"Authorization": f"Bearer {token}"}
            assert (await client.get("/api/v1/auth/me")).status_code == 401
            me = await client.get("/api/v1/auth/me", headers=headers)
            assert me.json()["data"]["roles"] == ["ADMIN"]
            assert (await client.get("/test/staff", headers=headers)).status_code == 200
            # Same token, changed DB role: authorization must be revoked immediately.
            async with engine.begin() as connection:
                await connection.execute(
                    text("DELETE FROM user_roles WHERE user_id = :id"), {"id": user}
                )
            assert (await client.get("/test/staff", headers=headers)).status_code == 403
            async with engine.begin() as connection:
                await IdentityRepository(connection).set_status(user, UserStatus.LOCKED)
            assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
            async with engine.begin() as connection:
                await IdentityRepository(connection).set_status(user, UserStatus.ACTIVE)
                await IdentityRepository(connection).soft_delete_user(user)
            assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
