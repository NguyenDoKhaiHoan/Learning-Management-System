"""Identity SQL primitives. Authentication/hash verification belong in application."""

from datetime import datetime

from src.core.database.sql import SqlRepository, SqlRow
from src.modules.identity_access.domain.enums import UserStatus


class IdentityRepository(SqlRepository):
    async def create_user(
        self,
        *,
        email: str,
        username: str,
        hashed_password: str,
        status: UserStatus = UserStatus.INACTIVE,
    ) -> int:
        return await self.insert(
            """INSERT INTO users (email, username, hashed_password, status)
               VALUES (:email, :username, :hashed_password, :status)""",
            {
                "email": email,
                "username": username,
                "hashed_password": hashed_password,
                "status": UserStatus(status).value,
            },
        )

    async def get_user(self, user_id: int) -> SqlRow | None:
        # Public projection intentionally excludes password hashes.
        return await self.fetch_one(
            """SELECT id, email, username, status, created_at, updated_at
               FROM users WHERE id = :id AND deleted_at IS NULL""",
            {"id": user_id},
        )

    async def get_credentials(self, email: str) -> SqlRow | None:
        """Internal auth lookup only; never serialize this row in an API response."""
        return await self.fetch_one(
            """SELECT id, email, username, hashed_password, status
               FROM users WHERE email = :email AND deleted_at IS NULL""",
            {"email": email},
        )

    async def set_status(self, user_id: int, status: UserStatus) -> bool:
        return bool(
            await self.execute(
                "UPDATE users SET status = :status WHERE id = :id AND deleted_at IS NULL",
                {"id": user_id, "status": UserStatus(status).value},
            )
        )

    async def soft_delete_user(self, user_id: int) -> bool:
        return bool(
            await self.execute(
                """UPDATE users SET deleted_at = CURRENT_TIMESTAMP(6)
               WHERE id = :id AND deleted_at IS NULL""",
                {"id": user_id},
            )
        )

    async def store_refresh_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        family_id: str,
        expires_at: datetime,
    ) -> int:
        return await self.insert(
            """INSERT INTO refresh_tokens (user_id, token_hash, family_id, expires_at)
               VALUES (:user_id, :token_hash, :family_id, :expires_at)""",
            {
                "user_id": user_id,
                "token_hash": token_hash,
                "family_id": family_id,
                "expires_at": expires_at,
            },
        )

    async def lock_refresh_token(self, token_hash: str) -> SqlRow | None:
        """Caller holds a transaction across lookup, reuse checks and rotation."""
        return await self.fetch_one(
            """SELECT id, user_id, family_id, expires_at, revoked_at FROM refresh_tokens
               WHERE token_hash = :token_hash FOR UPDATE""",
            {"token_hash": token_hash},
        )

    async def revoke_token_family(self, family_id: str) -> int:
        return await self.execute(
            """UPDATE refresh_tokens SET revoked_at = CURRENT_TIMESTAMP(6)
               WHERE family_id = :family_id AND revoked_at IS NULL""",
            {"family_id": family_id},
        )
