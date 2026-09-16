# Đối chiếu tuần 2 — 16/09/2026

Nguồn WBS là tab `Plan` tại URL trong `google-sheet.json`, đọc ngày 16/09/2026.
Các WBS `2.1`–`2.8` do phiên triển khai trước tự chia trong local chưa khớp nội dung
WBS gốc trên Sheet. Bản này sửa nội dung task local theo danh mục gốc; không đổi
WBS, tên task, owner, deadline, trọng số hoặc công thức trên Sheet.

Báo cáo trước “hoàn thành 4/8 = 50%” không phản ánh đúng kế hoạch gốc.
Các chức năng đã viết vẫn được giữ, nhưng được đối chiếu đúng task và phần còn thiếu.

## Task 2.1 — Login, password hashing, refresh/logout và account status

Checklist 5 đầu ra, mỗi đầu ra bằng nhau trong tỷ lệ nội bộ task:

- [x] Login cấp access JWT sau khi kiểm tra thông tin và trạng thái tài khoản.
- [x] Hash/verify mật khẩu PBKDF2-SHA256 có salt; kiểm tra đúng/sai và hash lỗi.
- [x] Chặn account inactive/locked/deleted; Admin có API cập nhật trạng thái.
- [ ] Refresh token rotation, kiểm tra expiry/reuse và test.
- [ ] Logout thu hồi refresh session/token và test.

Tỷ lệ: 3/5 = 60%. Bằng chứng: identity router, application/passwords.py,
core/security/dependencies.py, tests/unit/test_week1.py và test_week2_identity.py.
API status mới kiểm thử happy path bằng mock; nhánh status 404 chưa có test riêng.

## Task 2.2 — Role/permission API và resource authorization

Checklist 4 đầu ra, mỗi đầu ra bằng nhau trong tỷ lệ nội bộ task:

- [x] API Admin gán/thu hồi role có sẵn, có unit test happy path.
- [x] Backend role guard dùng role/account hiện tại trong SQL; test 401/403/200.
- [ ] Permission API và tích hợp guard trên route nghiệp vụ.
- [ ] Resource authorization: kiểm tra sở hữu/phạm vi course/enrollment và test.

Tỷ lệ: 2/4 = 50%. Bằng chứng: user_role/presentation/router.py,
core/security/dependencies.py, tests/unit/test_week1.py và test_week2_identity.py.
require_permissions đã có helper/test với route dành riêng cho test, chưa chứng minh
permission API hoàn thiện. Audit thay đổi quyền và integration các API Admin còn thiếu.

## Task 2.3–2.8

| WBS | Đầu ra gốc | Kết quả đối chiếu |
|---|---|---|
| 2.3 | CRUD Course cho Admin/Instructor | Chưa có API CRUD và resource scope |
| 2.4 | API module/lesson metadata, ordering và publish course | Chưa có API/publish policy và test |
| 2.5 | Enrollment API và course_staff; Active/Suspended | Chưa có API nghiệp vụ và test |
| 2.6 | Route guard và API client nền tảng frontend | Frontend chỉ có khung thư mục |
| 2.7 | Seed ba role, user mẫu, course và enrollment | Seed cũ chỉ có Student token-only |
| 2.8 | Test auth → publish → enrollment và demo tuần 2 | Chưa có luồng tích hợp/demo |

Các task này ở 0% theo đầu ra; schema/repository của tuần 1 không được tính là API hoàn thành.

## Kiểm chứng và tỷ lệ tổng hợp

- Backend: 45 test đạt; 1 integration test skip vì thiếu `MYSQL_TEST_ADMIN_URL`.
- Ruff và shared-contract drift check đạt.
- Test đồng bộ được sửa để cho phép thêm tuần mới và vẫn giữ 15 WBS tuần 1.
- Không tuyên bố đã test Postman end-to-end hoặc MySQL integration tuần 2.

Trọng số D20:D27 trên Sheet: 0.75, 0.5, 0.75, 0.75, 0.75, 0.5, 0.5, 0.5;
tổng 5. Tỷ lệ tuần 2 = (0.75 × 0.6 + 0.5 × 0.5) / 5 = 14%.
Đây là ước tính theo checklist công khai, không phải tỷ lệ test coverage hay nghiệm thu.
Chỉ F20:G20 và F21:G21 cần đổi từ 0 sang đang thực hiện; dòng tổng hợp 2.0 tự tính.
