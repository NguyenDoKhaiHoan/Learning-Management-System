# WBS 7.1 — Performance baseline

Checkpoint 19/10/2026: [số liệu gốc](week-7-baseline.json) chạy trên Windows,
Python 3.11.9, MySQL 8.0.45. Fixture tạo rồi xóa database `lms_test_<uuid>` và
storage tạm; không benchmark trên dữ liệu người dùng.

Tập dữ liệu: 12 khóa Published, 12 lesson, 201 enrollment trong khóa đo report;
gradebook rỗng là tình huống đo hiện tại. Mỗi endpoint warmup 3 lần, đo 40 request
ở concurrency 4. Job export 201 learner đo 10 lần, concurrency 1, gồm enqueue,
SQL, tạo CSV private và kiểm tra READY. Ghi p50/p95/max, throughput và SQL/op.
HTTPX gọi ASGI trong process; số liệu không bao gồm mạng, reverse proxy hoặc
antivirus và chưa phải kết luận sức tải production.

| Operation | p95 (ms) | SQL/op | Budget p95 (ms) |
|---|---:|---:|---:|
| Course catalog | 24.28 | 4 | 1000 |
| Student progress | 79.52 | 13 | 1000 |
| Learner report | 35.49 | 7 | 1000 |
| Gradebook report | 32.85 | 7 | 1000 |
| Admin overview | 23.24 | 4 | 1000 |
| Learner export (201 rows) | 45.33 | 32 | 2000 |

Không có lỗi trong các lượt đo. Các budget là gate phát hiện regression local,
không phải SLA. Student progress có nhiều SQL nhất trong nhóm request; dashboard
aggregate là ứng viên cache ở 7.3. Tiếp tục đo khi tăng learner/grade hoặc triển khai
qua proxy trước khi đặt SLA và quyết định index/cache tiếp theo.

Chạy tại `lms-platform/backend`, với `MYSQL_TEST_ADMIN_URL` đã cấu hình trong
environment (tài khoản tạo/xóa database thử):

```powershell
$env:BASELINE_OUTPUT = '../docs/testing/week-7-baseline-rerun.json'
../../.venv/Scripts/python -m pytest -q tests/performance/baseline.py --require-mysql
```

`BASELINE_SAMPLES` (10–1000, mặc định 40), `BASELINE_CONCURRENCY` (1–20, mặc định 4).
File benchmark được gọi tường minh, không chạy lẫn vào regression thông thường.
Status HTTP, số dòng và trạng thái job được assert; vượt budget làm lệnh thất bại.
