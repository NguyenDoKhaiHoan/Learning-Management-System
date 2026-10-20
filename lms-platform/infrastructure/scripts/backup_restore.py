"""Create and verify a MySQL logical backup, then restore it to a disposable DB.

The password is passed through MYSQL_PWD for the child process and is never part
of an argv list or the output.  Restore intentionally requires a separate target
database so a trial cannot overwrite the source by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import URL, make_url


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(backup: Path) -> Path:
    return backup.with_name(backup.name + ".sha256.json")


def parse_database_url(raw: str) -> URL:
    url = make_url(raw)
    if url.drivername not in {"mysql+aiomysql", "mysql", "mysql+pymysql"}:
        raise ValueError("DATABASE_URL must use a MySQL driver")
    if not url.host or not url.username or not url.database:
        raise ValueError("DATABASE_URL must include host, user and database")
    return url


def _client_env(url: URL) -> dict[str, str]:
    env = os.environ.copy()
    if url.password is not None:
        env["MYSQL_PWD"] = url.password
    return env


def _mysql_args(url: URL, database: str) -> list[str]:
    args = ["-h", url.host or "127.0.0.1", "-P", str(url.port or 3306), "-u", url.username or ""]
    if database:
        args.append(database)
    return args


def create_backup(raw_url: str, output: Path) -> Path:
    url = parse_database_url(raw_url)
    if shutil.which("mysqldump") is None:
        raise RuntimeError("mysqldump is required for backup")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "mysqldump",
        *_mysql_args(url, url.database or ""),
        "--single-transaction",
        "--routines",
        "--triggers",
        "--events",
        "--hex-blob",
        "--set-gtid-purged=OFF",
        "--skip-add-drop-database",
    ]
    with output.open("wb") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE,
                                env=_client_env(url), check=False)
    if result.returncode:
        output.unlink(missing_ok=True)
        raise RuntimeError("mysqldump failed; see local MySQL logs")
    manifest = {
        "backup": output.name,
        "sha256": checksum(output),
        "database": url.database,
        "created_at": datetime.now(UTC).isoformat(),
    }
    manifest_path(output).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def verify_backup(backup: Path) -> dict:
    backup = backup.resolve()
    manifest = json.loads(manifest_path(backup).read_text(encoding="utf-8"))
    actual = checksum(backup)
    if manifest.get("sha256") != actual:
        raise ValueError("Backup checksum does not match its manifest")
    return manifest


def restore_backup(raw_url: str, backup: Path, target_database: str) -> None:
    url = parse_database_url(raw_url)
    manifest = verify_backup(backup)
    if target_database == url.database:
        raise ValueError("Restore target must be different from the source database")
    if not target_database.startswith("lms_restore_"):
        raise ValueError("Restore target must start with lms_restore_")
    if not re.fullmatch(r"[A-Za-z0-9_]+", target_database):
        raise ValueError("Restore target contains unsupported characters")
    if shutil.which("mysql") is None:
        raise RuntimeError("mysql client is required for restore")
    create = subprocess.run(
        ["mysql", *_mysql_args(url, "")],
        input=(
            f"CREATE DATABASE IF NOT EXISTS `{target_database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
        ).encode(),
        stderr=subprocess.PIPE,
        env=_client_env(url),
        check=False,
    )
    if create.returncode:
        raise RuntimeError("mysql could not create the disposable restore database")
    command = ["mysql", *_mysql_args(url, target_database)]
    with backup.open("rb") as stream:
        result = subprocess.run(command, stdin=stream, stderr=subprocess.PIPE,
                                env=_client_env(url), check=False)
    if result.returncode:
        raise RuntimeError("mysql restore failed; see local MySQL logs")
    print(f"Restored {manifest['backup']} to {target_database}; checksum {manifest['sha256']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--file", type=Path, required=True)
    restore.add_argument("--target-database", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("--database-url or DATABASE_URL is required")
    if args.command == "backup":
        print(f"Created backup {create_backup(args.database_url, args.output)}")
    elif args.command == "restore":
        restore_backup(args.database_url, args.file, args.target_database)
    else:
        print(json.dumps(verify_backup(args.file), indent=2))


if __name__ == "__main__":
    main()
