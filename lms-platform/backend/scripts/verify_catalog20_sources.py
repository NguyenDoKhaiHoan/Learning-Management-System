"""Fetch each primary reference and record HTTP status, title and verification time."""

import argparse
import concurrent.futures
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import requests
import truststore

from scripts.catalog20_content import COURSES, validate_content


def fetch(course):
    response = requests.get(
        course.source_url, timeout=30, headers={"User-Agent": "LMS-Catalog-Source-Verification/1.0"}
    )
    match = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.S | re.I)
    return {
        "course": course.title,
        "url": course.source_url,
        "resolved_url": response.url,
        "status": response.status_code,
        "page_title": re.sub(r"\s+", " ", match.group(1)).strip() if match else "",
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "verified_at": datetime.now(UTC).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate_content()
    truststore.inject_into_ssl()
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        for course, result in zip(COURSES, executor.map(fetch, COURSES), strict=True):
            records.append(result)
            print(result["status"], course.source_url, flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if any(row["status"] != 200 for row in records):
        raise SystemExit("Some primary references could not be verified; inspect the source report")


if __name__ == "__main__":
    main()
