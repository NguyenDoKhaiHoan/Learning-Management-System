"""Password hashing primitives with a versioned, self-describing storage format."""

import base64
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    if not 8 <= len(password) <= 128:
        raise ValueError("Password length must be between 8 and 128 characters")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return "$".join(
        (
            ALGORITHM,
            str(ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    """Return False for malformed/legacy values without leaking parsing details."""
    try:
        algorithm, rounds, salt_text, digest_text = encoded.split("$", 3)
        iterations = int(rounds)
        if algorithm != ALGORITHM or not 100_000 <= iterations <= 1_000_000:
            return False
        salt = base64.b64decode(salt_text, altchars=b"-_", validate=True)
        expected = base64.b64decode(digest_text, altchars=b"-_", validate=True)
        if not 8 <= len(salt) <= 64 or len(expected) != 32:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(actual, expected)
    except (UnicodeError, ValueError):
        return False
