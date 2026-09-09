"""Access token primitives. No public token issuer until login is built in week 2."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from src.config.config import Settings


def create_access_token(user_id: int, settings: Settings) -> str:
    if not 0 < user_id <= 18446744073709551615:
        raise ValueError("Invalid user id")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
            "jti": uuid4().hex,
            "token_type": "access",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> int:
    if len(token) > 8192:
        raise jwt.InvalidTokenError("Token too long")
    claims = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "iss", "aud", "iat", "nbf", "exp", "jti", "token_type"]},
    )
    subject = claims["sub"]
    if (
        claims["token_type"] != "access"
        or not isinstance(claims["jti"], str)
        or not claims["jti"]
        or any(type(claims[key]) is not int for key in ("iat", "nbf", "exp"))
        or not isinstance(subject, str)
        or not subject.isascii()
        or not subject.isdecimal()
        or len(subject) > 20
        or not 0 < int(subject) <= 18446744073709551615
    ):
        raise jwt.InvalidTokenError("Invalid access token")
    return int(subject)
