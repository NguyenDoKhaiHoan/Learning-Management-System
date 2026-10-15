# MVP release candidate — WBS 6.6–6.8

Checkpoint: **15/10/2026**. Đây là runbook cho bản demo MVP có thể dựng lại từ
database trống, chạy regression đầy đủ và nghiệm thu ba vai trò.

## Chuẩn bị

Từ thư mục repository:

```powershell
cd lms-platform/backend
../../.venv/Scripts/python.exe -m alembic upgrade head
```

Đặt `DATABASE_URL`, `JWT_SECRET` và `APP_ENV=development` trong `backend/.env`.
Database demo phải là `lms` khi chạy thủ công; Playwright dùng `lms_demo_e2e` riêng.
Không dùng mật khẩu demo cho môi trường thật.

## Dựng demo

```powershell
cd lms-platform/backend
../../.venv/Scripts/python.exe -m scripts.run_demo
```

Seed tạo hoặc kiểm tra lại ba account ACTIVE, khóa `DEMO_WEEK2`, enrollment ACTIVE,
một assignment Published và một exam Published có question snapshot. Chạy seed lại
không ghi đè password, enrollment, progress hoặc lịch sử làm bài hiện có.

| Account | Role | Password mặc định |
| --- | --- | --- |
| `demo_admin` | ADMIN | `LmsDemo-Week2!2026` |
| `demo_instructor` | INSTRUCTOR | `LmsDemo-Week2!2026` |
| `demo_student` | STUDENT | `LmsDemo-Week2!2026` |

## Regression và release gate

Đặt `MYSQL_TEST_ADMIN_URL` trỏ tới một MySQL disposable có quyền tạo/xóa database,
sau đó chạy từ `lms-platform`:

```powershell
../.venv/Scripts/python.exe infrastructure/scripts/release_candidate.py
```

Gate bắt buộc chạy Ruff, full backend regression với `--require-mysql`, contract drift,
progress sync tests, frontend unit/build và Playwright E2E. `--skip-e2e` chỉ dành cho
vòng lặp local nhanh; không dùng kết quả đó làm biên bản release.

## Checklist nghiệm thu demo

- [ ] Ba account đăng nhập được và `/auth/me` trả đúng một role tương ứng.
- [ ] Student thấy `DEMO_WEEK2`, lesson và enrollment ACTIVE; route Admin/Instructor bị guard.
- [ ] Student thấy assignment Published, nộp text/PDF, xem lịch sử version và bị giới hạn attempt.
- [ ] Student thấy exam Published, bắt đầu attempt, autosave/resume, submit và không thấy đáp án đúng.
- [ ] Instructor xem submission/gradebook; Admin xem audit, security events và báo cáo export.
- [ ] Private file/CSV không lộ path, có `no-store` và `nosniff`; đổi quyền live chặn download.
- [ ] Full release gate hoàn thành không skip; kết quả và trace được ghi vào review tuần 6.

Sau nghiệm thu, dừng server demo và xóa database disposable. Database `lms` chỉ được
giữ lại khi cần trình diễn cục bộ.
