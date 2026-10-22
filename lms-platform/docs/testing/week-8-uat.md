# WBS 8.1 — UAT ba vai trò theo checklist nghiệp vụ

Biên bản UAT local ngày **22/10/2026**. UAT chạy trên MySQL 8.0 thật với database
disposable `lms_demo_e2e` và trình duyệt Chromium; seed demo tạo ba tài khoản
`demo_admin`, `demo_instructor` và `demo_student`. Mỗi test dùng dữ liệu riêng hoặc
fixture idempotent để không ghi đè database `lms`.

## Phạm vi và tiêu chí đạt

| Vai trò | Luồng được nghiệm thu | Tiêu chí quan sát |
| --- | --- | --- |
| Admin | Tài khoản/vai trò, audit, security event, báo cáo và export | Backend giữ scope theo role; UI lọc được dữ liệu, tải được CSV, không gọi route bị cấm |
| Instructor | Tạo và công bố course/content, ghi danh, exam, review anti-cheating, gradebook | Course/content CRUD, publish, duyệt learner, chấm và review hoạt động đúng |
| Student | Đăng nhập, My Courses, lesson, assignment, exam, notification/forum, grade | Chỉ thấy tài nguyên được cấp quyền; autosave/resume/submit và grade Published đúng |

Checklist business rule được đối chiếu với [MVP acceptance checklist](week-6-acceptance.md)
và [security checklist](week-6-security.md). Các lỗi 401/403, trạng thái Draft,
enrollment ACTIVE, giới hạn file và private download đều nằm trong regression hiện có.

## Bằng chứng chạy lại

Từ thư mục `lms-platform/backend`, đặt `MYSQL_TEST_ADMIN_URL` trỏ tới tài khoản
MySQL có quyền CREATE/DROP database rồi chạy:

```powershell
../../.venv/Scripts/python.exe -m pytest -q --strict-markers --require-mysql -m "acceptance or security"
```

Kết quả checkpoint: **11 passed, 125 deselected**.

Từ `lms-platform/frontend`, với MySQL local đang chạy:

```powershell
npm test
npm run build
npm run test:e2e
```

Kết quả checkpoint: **11 unit passed**, production build thành công và **12 browser
UAT tests passed**. Bộ browser bao phủ ba portal ở desktop/mobile, role guard,
course/content builder, assignment/exam/grade, audit/security và report/export.

## Quyết định UAT

Các tiêu chí trong phạm vi trên đạt tại checkpoint local. Bản ghi này là bằng chứng
nghiệm thu chức năng trước deployment rehearsal; kết quả remote CI và kiểm thử hạ tầng
production được ghi riêng ở [deployment rehearsal](week-8-deployment.md) và
[security review](week-8-security-review.md).
