# WBS 7.2 — Durable queue, retry và idempotency

Queue MySQL `export_jobs` được mở rộng bằng migration **0013_export_retries**.
`attempt_count` và `available_at` được lưu bền; worker chỉ lấy job PENDING đến hạn.
Lỗi I/O, timeout và SQL OperationalError được retry tối đa 3 lượt xử lý, với backoff
2, 4 giây (cấu hình được, cap 300 giây). Lỗi quyền/giới hạn dòng và lỗi lập trình
kết thúc FAILED ngay. Mỗi lần retry đều kiểm tra lại account, permission và course
scope, không dùng quyền đã lưu lúc enqueue.

Giữ thứ tự khóa requester → course → job trong transaction cho cả enqueue/worker.
Nhiều worker chỉ công bố một kết quả/audit READY. Cặp `(requested_by, request_id)`
là unique; gửi lại cùng payload trả cùng job, đổi payload nhận 409. Gửi lại request
không reset số lượt hoặc bỏ qua backoff. Requester khác có namespace riêng.

Khi thất bại, transaction kết quả rollback; file tạm/kết quả của lượt lỗi được dọn,
sau đó transaction riêng lưu retry hoặc FAILED kèm audit `export.retry/export.failed`.
UPDATE lỗi kiểm tra số lượt cũ để không ghi đè kết quả của worker khác.
Cancel có kiểm soát rollback và chờ thread đóng file trước khi dọn; restart tiếp tục
job PENDING. Hard kill có thể để lại file chưa được tham chiếu trong kho private;
việc thu gom file mồ côi cần đối chiếu metadata, không tự xóa dữ liệu đang dùng.

Environment:

```dotenv
EXPORT_MAX_ATTEMPTS=3
EXPORT_RETRY_BASE_SECONDS=2
EXPORT_TIMEOUT_SECONDS=120
```

API trạng thái job bổ sung `attempt_count`, `available_at`; PENDING đang chờ retry
có `error_code=EXPORT_RETRY`. Thành công xóa error code; cạn lượt chuyển FAILED.
Timeout giới hạn coroutine xử lý; khi đang ghi file, worker chờ thread đóng file để
cleanup an toàn. Payload export vẫn giới hạn 10.000 dòng và 3 job PENDING/requester.

Kiểm chứng: test MySQL inject lỗi sau khi đã ghi CSV, backoff, pool/worker mới,
hai worker đồng thời, concurrent enqueue, conflict payload, cạn lượt, timeout và
thu hồi quyền giữa hai lượt. Regression tuần 6 giữ kiểm tra cancel/restart,
audit rollback, row limit và quyền tải private.

```powershell
# Tại backend, MYSQL_TEST_ADMIN_URL đã cấu hình.
../../.venv/Scripts/python -m alembic upgrade head
../../.venv/Scripts/python -m pytest -q tests/integration/test_week7_jobs.py tests/integration/test_week6_reports.py --require-mysql
```
