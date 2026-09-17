"""Opaque refresh tokens, serialized per account to make family revocation atomic."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

from src.core.contracts import AccessToken
from src.core.security.jwt import create_access_token
from src.modules.audit_security.domain.enums import SecurityEventType
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.identity_access.infrastructure.repository import IdentityRepository


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_tokens(connection, settings, user_id: int, family_id: str | None = None):
    token = secrets.token_urlsafe(48)
    await IdentityRepository(connection).store_refresh_token(
        user_id=user_id,
        token_hash=token_digest(token),
        family_id=family_id or str(uuid4()),
        expires_at=datetime.now(UTC).replace(tzinfo=None)
        + timedelta(days=settings.refresh_token_expire_days),
    )
    return AccessToken(
        access_token=create_access_token(user_id, settings),
        refresh_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_days * 86400,
    )


async def consume_refresh(connection, settings, token: str, trace_id: str, *, logout=False):
    repo = IdentityRepository(connection)
    digest = token_digest(token)
    owner = await repo.fetch_one(
        "SELECT user_id FROM refresh_tokens WHERE token_hash = :hash", {"hash": digest}
    )
    if owner is None:
        raise HTTPException(401, headers={"WWW-Authenticate": "Bearer"})
    # All refresh operations for an account take this lock before token/family locks.
    user = await repo.fetch_one(
        "SELECT status, deleted_at FROM users WHERE id = :id FOR UPDATE",
        {"id": owner["user_id"]},
    )
    row = await repo.lock_refresh_token(digest)
    invalid = (
        row["revoked_at"] is not None
        or row["expires_at"] <= datetime.now(UTC).replace(tzinfo=None)
        or user["status"] != "ACTIVE"
        or user["deleted_at"] is not None
    )
    if logout or invalid:
        await repo.revoke_token_family(row["family_id"])
        await AuditRepository(connection).append_security_event(
            actor_id=owner["user_id"],
            event_type=SecurityEventType.TOKEN_REUSE_DETECTED
            if row["revoked_at"] is not None and not logout
            else SecurityEventType.TOKEN_REVOKED,
            trace_id=trace_id,
        )
        # Revocation must survive the HTTP 401 response.
        await connection.commit()
        if invalid and not logout:
            raise HTTPException(401, headers={"WWW-Authenticate": "Bearer"})
        return None
    await repo.execute(
        "UPDATE refresh_tokens SET revoked_at = UTC_TIMESTAMP(6) WHERE id = :id",
        {"id": row["id"]},
    )
    result = await issue_tokens(connection, settings, owner["user_id"], row["family_id"])
    await connection.commit()
    return result
