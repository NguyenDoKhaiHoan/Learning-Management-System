# WBS 7.4 — File scanning và bảo vệ storage

Checkpoint 19/10/2026: lesson resource và assignment submission chỉ được đưa từ
file `.upload` sang tên object cuối sau khi kiểm tra MIME/signature và scanner trả
`CLEAN`. Lỗi scanner trả 503 để client retry; kết quả nhiễm trả 422. Cả hai trường
hợp đều rollback metadata/submission và xóa file tạm/kết quả. Tên object do server
sinh, tên hiển thị đã loại path, giới hạn kích thước được kiểm tra trước và trong
khi stream.

Production/staging bắt buộc `FILE_SCAN_BACKEND=clamd`. Adapter gửi `zINSTREAM`
qua TCP private, chia chunk 64 KiB, có timeout và chỉ chấp nhận chính xác phản hồi
`stream: OK` hoặc `stream: ... FOUND`; kết nối lỗi, phản hồi lạ hoặc quá thời gian
đều fail closed. `development` chỉ so SHA-256 của EICAR để hỗ trợ local/test và bị
cấu hình từ chối ở staging/production; đây không phải malware engine.

```dotenv
FILE_SCAN_BACKEND=clamd
FILE_SCAN_HOST=clamd.internal
FILE_SCAN_PORT=3310
FILE_SCAN_TIMEOUT_SECONDS=30
```

Clamd phải nằm trên mạng private, không publish cổng ra Internet; cập nhật signature
theo vận hành của môi trường. `StreamMaxLength` phải lớn hơn hoặc bằng
`MAX_UPLOAD_BYTES`. API không gửi tên/path storage cho scanner và không chạy shell.

Migration **0015_file_scanning** thêm `scan_status`, `scan_engine`, `scanned_at`.
File mới được ghi `CLEAN` trong cùng transaction với metadata. File cũ mặc định
`PENDING`, không xuất hiện trong danh sách file và không tải được cho đến khi backfill:

```powershell
# Chạy nhiều lần theo batch sau khi clamd và DATABASE_URL đã sẵn sàng.
../../.venv/Scripts/python scripts/scan_pending_files.py --limit 100
```

Backfill kiểm tra containment, size và SHA-256 trước khi quét. File sạch chuyển
`CLEAN`; malware hoặc sai toàn vẹn chuyển `REJECTED`; scanner unavailable giữ
`PENDING` và dừng batch. Mỗi transition có audit `file.scan.clean/rejected`.
File REJECTED vẫn nằm trong private storage để điều tra/xử lý theo retention, không
được API phục vụ.

Mỗi download file upload kiểm tra live authorization, `scan_status=CLEAN`, path vẫn
nằm dưới private root, file tồn tại, size và SHA-256 khớp metadata; lỗi toàn vẹn trả
409. Response tiếp tục có `Cache-Control: no-store` và `X-Content-Type-Options: nosniff`.

Kiểm chứng gồm giao thức INSTREAM thật qua fake TCP scanner (clean/found/malformed),
scanner offline, cấu hình production, upload CLEAN, quarantine file legacy, backfill,
tamper detection, nhiễm/scanner unavailable không để lại DB/file và regression quyền,
path containment, lesson/submission version trên MySQL thật.

Full regression cuối đạt **133 backend tests** trên MySQL 8.0 với
`--require-mysql`, không skip integration. Hai cảnh báo còn lại là deprecation từ
FastAPI/Starlette test client dependency, không phải lỗi hành vi.

```powershell
../../.venv/Scripts/python -m pytest -q tests/unit/test_file_scanner.py `
  tests/integration/test_week7_storage.py tests/integration/test_week6_access_security.py `
  --require-mysql
```
