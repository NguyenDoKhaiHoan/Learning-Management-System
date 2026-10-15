"""Run the complete MVP release-candidate verification gate.

The gate intentionally requires a real disposable MySQL administrator URL.  A
successful run therefore cannot hide skipped integration tests behind a green
local-only result.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run(label: str, command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print(f"\n== {label} ==", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def npm_command() -> str:
    executable = "npm.cmd" if os.name == "nt" else "npm"
    path = shutil.which(executable)
    if path is None:
        raise SystemExit("npm is required for the frontend release checks")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Skip Playwright only for a fast local check; release evidence must include E2E.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not os.getenv("MYSQL_TEST_ADMIN_URL"):
        raise SystemExit(
            "MYSQL_TEST_ADMIN_URL is required; configure a disposable MySQL admin URL "
            "before running the release gate."
        )
    if not (BACKEND / "pyproject.toml").is_file():
        raise SystemExit(f"Backend not found: {BACKEND}")
    if not (FRONTEND / "package.json").is_file():
        raise SystemExit(f"Frontend not found: {FRONTEND}")

    env = os.environ.copy()
    python = sys.executable
    npm = npm_command()
    run(
        "backend lint",
        [python, "-m", "ruff", "check", "src", "tests", "scripts", "../database/migrations"],
        cwd=BACKEND,
        env=env,
    )
    run(
        "backend regression",
        [python, "-m", "pytest", "-q", "--strict-markers", "--require-mysql"],
        cwd=BACKEND,
        env=env,
    )
    run(
        "shared contracts",
        [python, "scripts/export_contracts.py", "--check"],
        cwd=BACKEND,
        env=env,
    )
    run(
        "progress sync tests",
        [python, "-m", "unittest", "discover", "-s", "lms-platform/progress/tests", "-v"],
        cwd=ROOT.parent,
        env=env,
    )
    run("frontend unit tests", [npm, "test"], cwd=FRONTEND, env=env)
    run("frontend build", [npm, "run", "build"], cwd=FRONTEND, env=env)
    if not args.skip_e2e:
        run("browser acceptance", [npm, "run", "test:e2e"], cwd=FRONTEND, env=env)
    print("\nRelease candidate checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
