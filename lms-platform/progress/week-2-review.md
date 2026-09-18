# Đối chiếu tuần 2 — 18/09/2026

**Cả 8 task tuần 2 đạt 100% ở local.** Bốn task còn lại 2.5–2.8 đã triển khai và
kiểm chứng qua MySQL thật và trình duyệt. Chưa đồng bộ checkpoint mới lên Sheet;
lần đồng bộ ngày 17/09 vẫn ghi nhận 55% cho cả tuần.

## Checkpoint hoàn thành 2.5–2.8

### 2.5 — Enrollment API và course_staff; Active/Suspended: 100%

- [x] Catalog khóa PUBLISHED để Student tìm khóa trước khi ghi danh, không trả nội dung.
- [x] Student gửi yêu cầu PENDING cho chính mình; Admin/Instructor đúng scope có thể tạo
  yêu cầu cho Student ACTIVE. Cấm tự chọn status/giả student khác, unique student-course.
- [x] List self và list manager; transition PENDING→ACTIVE, ACTIVE→SUSPENDED,
  SUSPENDED→ACTIVE; activation yêu cầu course PUBLISHED và account/role phù hợp.
- [x] Admin gán/đổi/gỡ course_staff; target ACTIVE có global role INSTRUCTOR;
  ASSISTANT không được sửa course. Thu hồi assignment có hiệu lực với access token cũ.
- [x] Audit cùng transaction; test lỗi audit rollback, concurrent duplicate/transition,
  cross-scope và staff bị gỡ trong lúc request chờ khóa course.

Bằng chứng: enrollment/application/service.py, presentation/router.py,
tests/integration/test_week2_remaining.py. Enrollment ACTIVE đọc được lesson;
SUSPENDED bị 403, khôi phục ACTIVE đọc lại được với cùng access token.

### 2.6 — Route guard và API client nền tảng frontend: 100%

- [x] TypeScript/Vite chạy/build được, shared types và proxy API.
- [x] Login và guard /admin, /instructor, /student, /courses/{id}; kiểm /auth/me mỗi navigation.
- [x] API client xử lý Bearer/envelope/trace, network/timeout, 401 refresh một lần,
  cùng một refresh cho nhiều request, 403 giữ phiên, logout chống response cũ phục hồi token.
- [x] Token chỉ trong bộ nhớ; không render HTML từ dữ liệu; loading/empty/error/success.
- [x] 11 unit tests; browser kiểm direct links, sai role, login lỗi và layout mobile không tràn.

Bằng chứng: frontend/src/services/api/client.ts, routes/guard.ts, app/main.ts,
tests/unit và tests/e2e/week2.spec.ts. Giao diện nền tảng đủ cho demo; full portal của
các tuần sau và pagination UI trên 100 mục không nằm trong đầu ra tuần 2.

### 2.7 — Seed ba role, user mẫu, course và enrollment: 100%

- [x] ADMIN/INSTRUCTOR/STUDENT, ba user ACTIVE với password PBKDF2 và permission cần thiết.
- [x] Course PUBLISHED, module/lesson, course_staff Instructor và enrollment ACTIVE.
- [x] Seed idempotent giữ ID và learning state; account xung đột không bị ghi đè.
- [x] Chỉ database demo/test; run_demo tạo DB riêng, migrate, seed và mở API.
- [x] MySQL tests kiểm login ba role, seed lặp, giữ enrollment SUSPENDED và chặn DB lms.

Bằng chứng: backend/scripts/seed_week2.py, run_demo.py và test_demo_seed.py.
Demo local đã khởi chạy ở API 8002, frontend 5173; không sửa database lms.

### 2.8 — Test auth → publish → enrollment và demo tuần 2: 100%

- [x] HTTP MySQL và browser thực: Instructor login → tạo course/module/lesson → publish →
  Student request enrollment → Instructor activate → Student đọc bài → suspend → Student bị 403.
- [x] 63 backend tests, 11 frontend unit tests, 3 browser E2E tests đạt; không skip MySQL.
- [x] TypeScript/Vite build, Ruff, shared-contract drift và 5 test sync đạt.
- [x] Kiểm tra ảnh desktop/mobile; CI thêm frontend build/unit/E2E (chưa chạy remote).
- [x] [Hướng dẫn demo và tài khoản](../docs/api/week-2-demo.md), [frontend README](../frontend/README.md).

Tổng tuần 2 local theo trọng số = 5/5 = **100%**. Không coi đây là UAT hoặc release production.

## Lịch sử checkpoint 17/09/2026

Hoàn thành 100% bốn task đầu theo WBS gốc: **2.1–2.4**. Task 2.5–2.8 giữ 0%.
Đã đồng bộ F20:G23 trên tab Plan và đọc lại xác nhận bốn task 100%, tổng tuần 2 là 55%.
Nhật ký tại last-sync.json. Danh mục/trọng số dựa trên
tab Plan đã đọc ngày 16/09/2026. Không đổi WBS, tên task, owner, deadline hoặc công thức.

## Checkpoint hoàn thành 2.1–2.4

### 2.1 — Login, password hashing, refresh/logout và account status: 100%

- [x] Login cấp access JWT sau khi xác minh mật khẩu/account status.
- [x] PBKDF2-SHA256 có salt, kiểm đúng/sai/hash lỗi.
- [x] Chặn inactive/locked/deleted; Admin đổi status, 404 nếu không tồn tại;
  khóa/inactive thu hồi mọi refresh token hiện có.
- [x] Refresh rotation, lưu hash, kiểm expiry, phát hiện reuse và revoke family.
- [x] Logout thu hồi family; kiểm thử logout lặp lại và token đã thu hồi.

Bằng chứng: identity_access/presentation/router.py, application/passwords.py,
application/sessions.py, tests/unit/test_week2_identity.py và integration/test_week2_mysql.py.
HTTP MySQL còn kiểm refresh đồng thời: một request thành công, một reuse 401,
token con cũng bị thu hồi. Logout thu hồi refresh session; access JWT còn hiệu lực
đến hết TTL và vẫn kiểm role/account từ SQL mỗi request.

### 2.2 — Role/permission API và resource authorization: 100%

- [x] Admin đọc/gán/thu hồi role có sẵn; thiếu resource 404, trùng assignment 409.
- [x] Role guard lấy role/account hiện tại từ SQL; role bị thu hồi chặn cùng access token.
- [x] Permission catalog và API đọc/cấp/thu hồi permission theo role; guard trên
  course read/write/publish và content routes. Thu hồi có hiệu lực với token đã phát.
- [x] Scope Admin toàn hệ thống, Instructor owner hoặc course_staff INSTRUCTOR;
  người học chỉ đọc course PUBLISHED có enrollment ACTIVE của chính mình.

Audit role/permission/account cùng transaction với thay đổi. HTTP MySQL kiểm
401/403/404/409/422, cross-course/parent, enrollment PENDING/SUSPENDED.
API quản lý enrollment/course_staff còn ở 2.5; scope hiện tại đọc dữ liệu đã có trong DB.
Catalog khóa học gồm course.read/write/publish; Admin bootstrap grant qua permission API.

### 2.3 — CRUD Course cho Admin/Instructor: 100%

- [x] POST, GET list/detail, PUT và DELETE soft-delete.
- [x] Validation code/title/description, unique code, pagination và filter status.
- [x] Owner lấy từ tài khoản hiện tại; guard role/permission và scope course.
- [x] Audit tạo/sửa/xóa cùng transaction; lỗi audit rollback business write.
- [x] HTTP MySQL kiểm CRUD, 403 khác scope, 404 missing/deleted, 409 duplicate, 422 input.

Bằng chứng: course/application/service.py, course/presentation/router.py và
test_course_crud_scope_validation_and_soft_delete,
test_audit_failure_rolls_back_business_write trong integration/test_week2_mysql.py.

### 2.4 — API module/lesson metadata, ordering và publish course: 100%

- [x] Tạo/đọc/sửa/xóa metadata module/lesson; kiểm parent và soft-delete ancestors.
- [x] Order toàn bộ sibling, không lặp/thiếu/khác parent; transaction hỗ trợ swap,
  kể cả khi có hàng đã soft-delete, không xung đột UNIQUE.
- [x] DRAFT → PUBLISHED; PUBLISHED → DRAFT/ARCHIVED; ARCHIVED → DRAFT.
- [x] Publish cần module, mỗi module có lesson và mọi lesson có content không rỗng;
  chỉ sửa metadata/ordering hoặc xóa ở DRAFT.
- [x] Guard/audit và MySQL tests cho CRUD, order, invalid transitions, publish đồng thời,
  và publish đọc nội dung mới nhất sau khi chờ khóa course.

Bằng chứng: learning_content/application/service.py, presentation/router.py,
course/application/service.py và integration/test_week2_mysql.py.
Endpoint/chính sách: [docs/api/week-2.md](../docs/api/week-2.md).
Schema 14 bảng/migration 0001_p0 vẫn đáp ứng; không thêm migration.

### Kiểm chứng ngày 17/09

- Backend: **55 passed, không skip**, chạy với MySQL thực trong database ngẫu nhiên
  lms_test_*; gồm migration upgrade/downgrade, SQL constraints và 9 scenario HTTP mới.
- Ruff: src, tests và database/migrations đạt.
- Shared OpenAPI: export và drift check đạt; cập nhật TypeScript transport types.
- Progress: 5 test sync đạt và sync.py --local xác nhận trạng thái hợp lệ.
- Không sửa dữ liệu database lms; chưa chạy remote CI hoặc demo toàn tuần.

Trọng số đã ghi nhận: 0.75, 0.5, 0.75, 0.75, 0.75, 0.5, 0.5, 0.5; tổng 5.
Tỷ lệ tuần 2 = (0.75 + 0.5 + 0.75 + 0.75) / 5 = **55%**.
Bốn task yêu cầu đều 100%; 55% là tỷ lệ cả tuần, không phải test coverage hoặc UAT.

## Lịch sử checkpoint 16/09/2026 (đã được thay thế bởi checkpoint trên)

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
