"""Private learning-file validation policy."""

from pathlib import Path, PurePath

from fastapi import HTTPException

ALLOWED_MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "text/plain": ".txt",
    "video/mp4": ".mp4",
}


def normalized_mime(value: str | None) -> str:
    mime = (value or "").split(";", 1)[0].strip().lower()
    if mime not in ALLOWED_MIME_EXTENSIONS:
        raise HTTPException(422, "Unsupported file MIME type")
    return mime


def safe_display_name(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name.strip()
    if not name or len(name) > 255 or any(ord(char) < 32 for char in name):
        raise HTTPException(422, "Invalid file name")
    return name


def validate_file_content(path: Path, mime_type: str) -> None:
    with path.open("rb") as source:
        prefix = source.read(4096)
    valid = {
        "application/pdf": prefix.startswith(b"%PDF-"),
        "image/jpeg": prefix.startswith(b"\xff\xd8\xff"),
        "image/png": prefix.startswith(b"\x89PNG\r\n\x1a\n"),
        "video/mp4": len(prefix) >= 12 and prefix[4:8] == b"ftyp",
        "text/plain": b"\x00" not in prefix,
    }[mime_type]
    if mime_type == "text/plain" and valid:
        try:
            prefix.decode("utf-8")
        except UnicodeDecodeError:
            valid = False
    if not valid:
        raise HTTPException(422, "File content does not match declared MIME type")
