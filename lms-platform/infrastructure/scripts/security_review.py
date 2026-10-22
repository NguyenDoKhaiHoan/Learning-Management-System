"""Run repeatable pre-release security policy checks for the LMS repository."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SAFE_SECRET_FILES = {".env.example"}


def tracked_secret_check() -> None:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT.parent, check=True, capture_output=True, text=True
    )
    unsafe = []
    for raw in result.stdout.splitlines():
        path = Path(raw)
        parts = set(path.parts)
        if ".secrets" in parts or path.suffix.lower() in {".pem", ".key"}:
            unsafe.append(raw)
        if path.name.startswith(".env") and path.name not in SAFE_SECRET_FILES:
            unsafe.append(raw)
    if unsafe:
        raise RuntimeError("tracked secret-like files: " + ", ".join(unsafe))


def config_policy_check() -> None:
    sys.path.insert(0, str(BACKEND))
    from pydantic import ValidationError
    from src.config.config import Settings

    common = {
        "_env_file": None,
        "database_url": "mysql+aiomysql://user:password@db.example/lms?charset=utf8mb4",
        "jwt_secret": "week8-security-review-secret-0123456789",
    }
    try:
        Settings(**common, app_env="production", file_scan_backend="development")
    except ValidationError:
        pass
    else:
        raise RuntimeError("production accepted the development file scanner")
    try:
        Settings(**common, app_env="production", email_delivery_enabled=True, smtp_starttls=False)
    except ValidationError:
        pass
    else:
        raise RuntimeError("production accepted email delivery without STARTTLS")
    Settings(**common, app_env="production", file_scan_backend="clamd")


def run_security_tests() -> None:
    if not os.getenv("MYSQL_TEST_ADMIN_URL"):
        raise SystemExit("--run-tests requires MYSQL_TEST_ADMIN_URL in the environment")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--strict-markers",
            "--require-mysql",
            "-m",
            "security",
        ],
        cwd=BACKEND,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-tests", action="store_true", help="also run the MySQL security marker")
    args = parser.parse_args()
    tracked_secret_check()
    config_policy_check()
    if args.run_tests:
        run_security_tests()
    print("Security review policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
