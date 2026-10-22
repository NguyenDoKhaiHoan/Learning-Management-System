# WBS 8.3 — Deployment rehearsal

Deployment rehearsal kiểm tra đường đi từ database rỗng đến release seed mà không
đụng database ứng dụng. Script tạo database có tên bắt đầu bằng
`lms_test_rehearsal_`, chạy toàn bộ Alembic migration, seed ba role và fixture
assignment/exam, kiểm tra head/count rồi tự xóa database.

## Chạy rehearsal

Từ thư mục `lms-platform`, đặt `MYSQL_TEST_ADMIN_URL` trong môi trường riêng (không
ghi password vào repository) và chạy:

```powershell
../.venv/Scripts/python.exe infrastructure/scripts/deployment_rehearsal.py
```

Có thể dùng `--keep` để kiểm tra database sau rehearsal; chỉ tên database do script
sinh ra mới được phép giữ/xóa. Kết quả JSON không in URL hoặc secret, ví dụ:

```json
{"counts":{"assignments":1,"enrollments":1,"exams":1,"roles":3,"users":3},"database":"lms_test_rehearsal_xxxxxxxx","dropped":true,"migration_head":"0017_forum_moderation"}
```

## Acceptance gate

- `alembic upgrade head` chạy thành công trên database rỗng.
- `alembic_version` có đúng một head `0017_forum_moderation`.
- Seed tạo đủ ba user/role ACTIVE, enrollment ACTIVE, assignment Published và exam
  Published; chạy lại seed không ghi đè dữ liệu học tập.
- `/livez` và `/healthz` được kiểm tra khi khởi động app demo; `/metrics` không chứa
  query string, body, token hoặc credential.
- Database rehearsal bị xóa sau khi kiểm tra, trừ khi người vận hành chủ động dùng
  `--keep` để điều tra.

## Kết quả checkpoint

Ngày **22/10/2026**, rehearsal local chạy với MySQL 8.0 Windows và đạt migration head,
đủ fixture counts ở trên. Docker Desktop không cần cho đường chạy này; production vẫn
phải chạy migration trước khi mở traffic và lấy secret từ secret manager.
