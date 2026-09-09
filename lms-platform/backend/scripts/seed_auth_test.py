"""Create one local token-only Postman user. Run manually, never at app startup."""

import asyncio
import json

from sqlalchemy import text

from src.config.config import get_settings
from src.core.database.database import build_engine

EMAIL = "postman.test@example.com"
USERNAME = "postman_test"
DISABLED_PASSWORD = "!postman-token-only-no-password-login"


async def main() -> None:
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise RuntimeError("Test seed is restricted to development/test environments")
    engine = build_engine(settings)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(
                text(
                    """SELECT id, username, status, deleted_at, hashed_password FROM users
                   WHERE email = :email FOR UPDATE"""
                ),
                {"email": EMAIL},
            )
            user = result.mappings().one_or_none()
            if user is None:
                inserted = await connection.execute(
                    text(
                        """INSERT INTO users (email, username, hashed_password, status)
                       VALUES (:email, :username, :password, 'ACTIVE')"""
                    ),
                    {"email": EMAIL, "username": USERNAME, "password": DISABLED_PASSWORD},
                )
                user_id = int(inserted.lastrowid)
            else:
                if (
                    user["username"] != USERNAME
                    or user["status"] != "ACTIVE"
                    or user["deleted_at"] is not None
                    or user["hashed_password"] != DISABLED_PASSWORD
                ):
                    raise RuntimeError("Existing account differs from test seed; left unchanged")
                user_id = user["id"]
            await connection.execute(
                text(
                    """INSERT INTO roles (code, name) VALUES ('STUDENT', 'Student')
                   ON DUPLICATE KEY UPDATE code = code"""
                )
            )
            await connection.execute(
                text(
                    """INSERT INTO user_roles (user_id, role_id)
                   SELECT :user_id, id FROM roles WHERE code = 'STUDENT'
                   ON DUPLICATE KEY UPDATE user_id = user_id"""
                ),
                {"user_id": user_id},
            )
        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """SELECT id, email, username, status FROM users
                   WHERE id = :id AND status = 'ACTIVE' AND deleted_at IS NULL"""
                        ),
                        {"id": user_id},
                    )
                )
                .mappings()
                .one()
            )
            print(json.dumps(dict(row)))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
