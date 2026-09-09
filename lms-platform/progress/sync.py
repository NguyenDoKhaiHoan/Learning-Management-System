"""Synchronize reviewed LMS task status to existing Google Sheet F/G cells.

No spreadsheet creation, formatting or formula authoring. Default remote mode is
preview; --apply writes only matched task cells. --local needs no Google access.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
STATUSES = {"Đã hoàn thành", "Đang thực hiện", "Chưa thực hiện"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_tasks(tasks):
    seen = set()
    for task in tasks:
        wbs = task["wbs"]
        if not isinstance(wbs, str) or wbs in seen:
            raise ValueError("WBS phải là chuỗi duy nhất: " + str(wbs))
        seen.add(wbs)
        value = task["progress"]
        if type(value) not in (int, float) or not 0 <= value <= 1:
            raise ValueError(f"{wbs}: progress phải từ 0 đến 1")
        expected = "Đã hoàn thành" if value == 1 else "Chưa thực hiện" if value == 0 else "Đang thực hiện"
        if task["status"] not in STATUSES or task["status"] != expected:
            raise ValueError(f"{wbs}: status và progress không nhất quán")
        if not task.get("evidence") or not task.get("verified_at"):
            raise ValueError(f"{wbs}: cần evidence và verified_at")
        if not task.get("sheet_titles"):
            raise ValueError(f"{wbs}: cần tên công việc để kiểm tra hàng đích")


def plan_updates(rows, tasks, sheet_name, first_row):
    """Match stable WBS + reviewed title; refuse ambiguous IDs and formula cells."""
    indexed = {}
    for number, values in enumerate(rows, first_row):
        if not values or values[0] == "":
            continue
        key = str(values[0]).strip()
        if key in indexed:
            raise ValueError(f"WBS {key} bị trùng trong Google Sheet; chưa ghi dữ liệu")
        indexed[key] = (number, values)
    changes = []
    prefix = "'" + sheet_name.replace("'", "''") + "'"
    for task in tasks:
        key = task["wbs"]
        if key not in indexed:
            raise ValueError(f"Không tìm thấy WBS {key}; kiểm tra đúng tab/link Master Plan")
        number, row = indexed[key]
        if len(row) < 2 or str(row[1]).strip() not in task["sheet_titles"]:
            raise ValueError(f"WBS {key}: tên task không khớp; cần đối chiếu trước khi ghi")
        old = (row + [""] * 7)[5:7]
        if any(isinstance(v, str) and v.startswith("=") for v in old):
            raise ValueError(f"WBS {key}: F/G có công thức; không được ghi đè")
        new = [task["status"], task["progress"]]
        if old != new:
            changes.append({"wbs": key, "old": old, "new": new,
                            "range": f"{prefix}!F{number}:G{number}"})
    return changes


def connect(config):
    match = re.fullmatch(
        r"https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)(?:/[^\s]*)?",
        config["spreadsheet_url"].strip(),
    )
    if not match:
        raise ValueError("Điền link https://docs.google.com/spreadsheets/d/... vào google-sheet.json")
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession

    credential_path = Path(config["credentials_file"])
    if not credential_path.is_absolute():
        credential_path = ROOT / credential_path
    if not credential_path.is_file():
        raise ValueError("Thiếu credentials. Làm bước kết nối một lần trong README.md")
    credentials = Credentials.from_service_account_file(
        str(credential_path), scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return AuthorizedSession(credentials), f"https://sheets.googleapis.com/v4/spreadsheets/{match[1]}"


def fetch_rows(session, base, config):
    name = config["sheet_name"].replace("'", "''")
    target = quote(f"'{name}'!A{config['first_task_row']}:G", safe="")
    response = session.get(base + "/values/" + target,
                           params={"valueRenderOption": "FORMULA"}, timeout=30)
    if response.status_code != 200:
        raise ValueError(f"Đọc Google Sheet thất bại (HTTP {response.status_code}); kiểm tra link/quyền")
    return response.json().get("values", [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Ghi trạng thái lên Google Sheet")
    mode.add_argument("--local", action="store_true", help="Kiểm tra tiến độ local; không gọi Google")
    args = parser.parse_args()
    tasks = read_json(ROOT / "tasks.json")["tasks"]
    validate_tasks(tasks)
    if args.local:
        for task in tasks:
            print(f"{task['wbs']:5} {task['status']:18} {task['progress']:.0%}  {task['title']}")
        print(f"\n{sum(t['progress'] == 1 for t in tasks)}/{len(tasks)} task đang theo dõi đã hoàn thành.")
        return
    config = read_json(ROOT / "google-sheet.json")
    if not isinstance(config["first_task_row"], int) or config["first_task_row"] < 1:
        raise ValueError("first_task_row phải là số nguyên dương")
    session, base = connect(config)
    with session:
        rows = fetch_rows(session, base, config)
        changes = plan_updates(rows, tasks, config["sheet_name"], config["first_task_row"])
        preview = {"sheet": config["spreadsheet_url"], "changes": changes}
        (ROOT / "preview.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
        for change in changes:
            print(f"{change['wbs']}: {change['old']} -> {change['new']}")
        if not args.apply:
            print(f"Preview: {len(changes)} thay đổi; chưa ghi Google Sheet. Dùng --apply để đồng bộ.")
            return
        if not changes:
            print("Google Sheet đã khớp; không cần cập nhật.")
            return
        # Detect changes since the preview read; Sheets values API has no atomic compare-and-set.
        if fetch_rows(session, base, config) != rows:
            raise ValueError("Sheet vừa thay đổi; hãy chạy lại để tránh ghi lên chỉnh sửa đang diễn ra")
        response = session.post(base + "/values:batchUpdate", json={
            "valueInputOption": "RAW",
            "data": [{"range": c["range"], "values": [c["new"]]} for c in changes],
        }, timeout=30)
        if response.status_code != 200:
            raise ValueError(f"Đồng bộ thất bại (HTTP {response.status_code}); chạy preview để kiểm tra lại")
        after = fetch_rows(session, base, config)
        if plan_updates(after, tasks, config["sheet_name"], config["first_task_row"]):
            raise ValueError("Đã ghi nhưng kiểm tra lại chưa khớp; xem Google Sheet trước khi chạy lại")
        preview["synced_at"] = datetime.now(timezone.utc).isoformat()
        (ROOT / "last-sync.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Đã đồng bộ và kiểm tra lại {len(changes)} task. Giữ nguyên định dạng và các cột khác.")


if __name__ == "__main__":
    # CLI entry point only: use OS certificate trust, including Windows corporate CA.
    import truststore
    truststore.inject_into_ssl()
    try:
        main()
    except (ValueError, KeyError, FileNotFoundError, ImportError) as error:
        print(f"Chưa đồng bộ: {error}")
        raise SystemExit(1) from None
