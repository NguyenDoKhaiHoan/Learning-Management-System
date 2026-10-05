# Checkpoint 05/10/2026 — WBS 5.1–5.3

## Phạm vi nghiệm thu

- **5.1**: layout chung; form dùng chung chống submit kép, nhãn truy cập chính xác;
  API client giữ token trong memory, refresh/retry; route con/query guard theo role;
  loading/empty/error + retry/forbidden/success, generation guard bỏ response cũ;
  sidebar giữ active state khi lọc/phân trang.
- **5.2**: Admin quản lý tài khoản: tạo/sửa metadata, tìm/lọc/phân trang, trạng thái,
  gán/gỡ role và quyền theo role; course oversight CRUD/status/staff/enrollment
  nền tảng và báo cáo tổng quan/toàn hệ thống + từng course.
- **5.3**: dashboard số liệu của Instructor theo course sở hữu/phân công;
  course/content builder: metadata, chương/bài học CRUD, loại bài/preview, sắp xếp,
  LINK/FILE resource, completion rule có grade gate; publish/Draft/archive;
  editor chỉ ở Draft, xóa có xác nhận và backend scope enforcement.

## Bằng chứng kiểm chứng

- Backend **93 passed**, không skip, MySQL thật trên máy: toàn bộ regression
  tuần 1–4 + 3 acceptance mới tuần 5. Schema round-trip/canonical import đạt.
- Admin acceptance kiểm unauthorized/forbidden, pagination không trùng,
  search/status, tạo/sửa/unique conflict, password validation, role/status/login lock,
  response không có credentials, audit và rollback user + role khi audit lỗi.
- Report acceptance kiểm tổng user/course, publication, pagination, ownership,
  staff grant/revoke, enrollment, soft delete và live permission revoke.
- Frontend **11 unit passed**, build đạt. **7 Playwright E2E passed**, gồm 3 case
  cũ và 4 case mới: account/role/status/report, builder CRUD/reorder/resource/rule/
  publish/delete, nested forbidden guard không gửi admin request, loading/503/retry/
  stale response. Sau chỉnh nhãn/menu, 2 case Admin/builder chạy lại đạt.
- Ruff, contract drift, 5 progress sync tests và kiểm tra định dạng đạt.
- Browser plugin không có phiên khả dụng; dùng Playwright sẵn trong repo để kiểm tra
  và chụp ảnh desktop/mobile, đã rà soát trực quan báo cáo/tài khoản/dashboard.

## Database và demo đang chạy

- **lms** là database chính, head **0008_assessment_completion**; không tạo database
  ứng dụng mới. Các lms_test_* được fixture tạo và tự dọn; lms_demo_e2e chỉ dùng test UI.
- Seed thêm 8 course SHOWCASE_* (24 chương, 48 bài), assignment, enrollment,
  submission/progress; giữ dữ liệu cũ và checkpoint exam tuần 4.
- API http://127.0.0.1:8002; frontend http://127.0.0.1:5173.
- `node scripts/check-week5.mjs` xác minh trực tiếp UI dùng lms: Admin users/reports,
  DEMO_WEEK4 trong report và 1 learner hoàn thành, Instructor dashboard/React Draft
  builder, desktop/mobile không overflow; không có API/browser errors.
- Ảnh được lưu trong .local-logs và frontend/test-results, đều Git ignored.
  Uploaded private storage mới được Git ignored, không đưa dữ liệu upload vào commit.

Hướng dẫn API/demo: [week-5.md](../docs/api/week-5.md).
Chỉ thêm 5.1–5.3 vào tasks.json và sync F/G của ba task này. 5.4–5.8 giữ nguyên
trên sheet. Không nghiệm thu trước Student/exam/grade/notification/forum UI tuần 5.
