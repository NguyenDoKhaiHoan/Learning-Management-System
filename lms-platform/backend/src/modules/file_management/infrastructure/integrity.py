"""Private storage containment and digest checks before a download is served."""

import hashlib
import hmac

from fastapi import HTTPException


def verified_private_path(root, location, size_bytes, sha256):
    if not isinstance(size_bytes, int) or not isinstance(sha256, str):
        raise HTTPException(409, "Stored file is missing integrity metadata")
    root = root.resolve()
    try:
        path = (root / location).resolve(strict=True)
    except (OSError, RuntimeError):
        raise HTTPException(404) from None
    if root not in path.parents or not path.is_file():
        raise HTTPException(404)
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as source:
            while chunk := source.read(65536):
                size += len(chunk)
                digest.update(chunk)
    except OSError:
        raise HTTPException(404) from None
    if size != size_bytes or not hmac.compare_digest(digest.hexdigest(), sha256):
        raise HTTPException(409, "Stored file failed its integrity check")
    return path
