"""Scan legacy private files after migration 0015; fail closed if clamd is unavailable."""

import argparse
import asyncio

from fastapi import HTTPException

from src.config.config import get_settings
from src.core.database.database import build_engine
from src.jobs.processors.file_scanning import scan_pending_files


async def run(limit):
    settings = get_settings()
    engine = build_engine(settings)
    try:
        return await scan_pending_files(engine, settings, limit)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, choices=range(1, 1001), metavar="1..1000")
    args = parser.parse_args()
    try:
        processed = asyncio.run(run(args.limit))
    except HTTPException as error:
        raise SystemExit(f"Scan stopped: {error.detail}") from None
    print(f"Processed {processed} pending private files.")


if __name__ == "__main__":
    main()
