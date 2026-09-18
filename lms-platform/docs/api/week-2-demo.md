# Demo tuần 2 — auth → publish → enrollment → học nội dung

Checkpoint 18/09/2026. Backend MySQL thật, frontend TypeScript/Vite.

## Chuẩn bị

Từ root repository, mở hai terminal:

```powershell
# Terminal 1
cd lms-platform/backend
../../.venv/Scripts/python -m scripts.run_demo
```

```powershell
# Terminal 2
cd lms-platform/frontend
npm ci
npm run dev
```

Frontend: http://127.0.0.1:5173. API: http://127.0.0.1:8002/docs.
Database `lms_demo_week2` được tạo riêng, migrate head rồi seed trong một transaction;
không sửa dữ liệu database `lms`. Script dùng thông tin MySQL trong backend/.env,
chỉ cho phép môi trường development/test và tên DB `lms_demo_*`.
Đổi tên demo bằng `LMS_DEMO_DATABASE`, cổng API bằng `LMS_DEMO_PORT`;
nếu đổi cổng, đặt `LMS_API_TARGET` tương ứng khi chạy frontend.

| Tài khoản | Vai trò | Mật khẩu demo |
|---|---|---|
| demo_admin | ADMIN | LmsDemo-Week2!2026 |
| demo_instructor | INSTRUCTOR | LmsDemo-Week2!2026 |
| demo_student | STUDENT | LmsDemo-Week2!2026 |

Cả ba account ACTIVE và đăng nhập được; Admin/Instructor có course.read/write/publish,
Student có course.read. Khóa DEMO_WEEK2 có module, lesson, staff Instructor và enrollment
ACTIVE cho demo_student. Có thể dùng `LMS_DEMO_PASSWORD` khi tạo mới; seed chạy lại giữ
IDs/trạng thái học và từ chối overwrite account xung đột. Không dùng mật khẩu demo cho môi trường thật.

Nếu đã có database demo/test đã migrate và muốn chỉ seed, từ backend chạy
`../../.venv/Scripts/python -m scripts.seed_week2` với DATABASE_URL trỏ đúng database đó.
Seed từ chối DB không có prefix lms_demo_/lms_test_ trước khi thực hiện SQL.

## Kịch bản demo thủ công

1. Đăng nhập demo_instructor. Tạo khóa học với code mới, ví dụ DEMO_SESSION_001.
2. Thêm chương và bài học có nội dung; chọn **Công bố khóa học**.
3. Đăng xuất, đăng nhập demo_student. Tìm khóa vừa tạo trong **Khám phá khóa học**.
4. Chọn **Gửi yêu cầu ghi danh**; khóa xuất hiện ở **Khóa học của tôi**, trạng thái Chờ duyệt.
   Thử mở trực tiếp URL khóa học vẫn bị từ chối 403.
5. Đăng xuất, đăng nhập demo_instructor; mở khóa và chọn **Kích hoạt** trong phần Ghi danh.
6. Đăng nhập lại demo_student; chọn **Vào học**, mở bài để đọc nội dung.
7. Instructor chọn **Tạm ngưng** enrollment; Student mở lại khóa sẽ bị 403.
   Instructor có thể kích hoạt lại để khôi phục quyền đọc.
8. Student truy cập `/#/admin` hoặc `/#/instructor` bị route guard từ chối.
9. Đăng nhập demo_admin để xem tất cả khóa và phân công/gỡ giảng viên bằng mã user.
   Lấy mã tài khoản giảng viên từ `GET /api/v1/auth/me` khi đăng nhập giảng viên.

Gỡ course_staff không gỡ quyền của chính người tạo khóa: Instructor owner vẫn quản lý khóa
do mình tạo. Chỉ Instructor được phân công thêm mới mất phạm vi khi bị gỡ.
Frontend giữ token trong bộ nhớ; reload toàn bộ trang yêu cầu đăng nhập lại.

## API enrollment/staff

Prefix `/api/v1`; Bearer token, envelope và trace ID như [API tuần 2](week-2.md).

| Method/path | Quy tắc/body |
|---|---|
| GET /catalog/courses | course.read; metadata khóa PUBLISHED; không trả lesson content |
| GET /enrollments/me | course.read; enrollment của chính user, gồm title và course_status |
| POST /courses/{id}/enrollments | Student gửi `{}` để ghi danh chính mình; manager gửi `{student_id}` |
| GET /courses/{id}/enrollments | Admin/Instructor manager + course.read, list trong phạm vi |
| PATCH /courses/{id}/enrollments/{student_id} | Manager + course.write; `{status:"ACTIVE"}` hoặc `{status:"SUSPENDED"}` |
| GET /courses/{id}/staff | Manager + course.read |
| PUT /courses/{id}/staff/{user_id} | Admin + course.write; `{role:"INSTRUCTOR"}` hoặc `{role:"ASSISTANT"}` |
| DELETE /courses/{id}/staff/{user_id} | Admin + course.write; gỡ phân công, không xóa account |

List catalog/enrollment hỗ trợ limit 1..100, offset >=0. Enrollment POST trả 201/PENDING,
không cho client truyền status/owner tùy ý. Mỗi cặp student-course duy nhất; trùng trả 409.
Tài khoản nhận ghi danh phải ACTIVE và có role STUDENT; account không tồn tại/deleted trả
404, sai trạng thái/role trả 409. Chỉ nhận ghi danh/activate trong khóa PUBLISHED.
Transition: PENDING→ACTIVE, ACTIVE→SUSPENDED, SUSPENDED→ACTIVE; còn lại 409.
COMPLETED nằm trong schema nhưng chưa có API đánh dấu hoàn thành ở tuần 2.
Course_staff target cần ACTIVE + global role INSTRUCTOR; ASSISTANT không được sửa khóa học.
Staff PUT idempotent. Staff DELETE không có assignment trả 404.
Các mutation ghi audit cùng transaction; lỗi audit rollback mutation.

## Kết quả kiểm chứng

- 63 test backend đạt, không skip; migration upgrade/downgrade và SQL thật trên lms_test_*.
- 11 frontend unit tests đạt: Bearer/envelope/error trace, refresh đồng thời, retry giới hạn,
  logout race, lỗi mạng và route guard theo role.
- 3 browser E2E tests: luồng publish/enrollment, route guard desktop/mobile và Admin/login lỗi.
- TypeScript/build production, Ruff và shared-contract drift check đạt.
- Seed chạy lặp lại giữ ID và enrollment SUSPENDED; account xung đột không bị ghi đè.

Chạy tự động từ frontend: `npm run test:e2e` (sau `npx playwright install chromium`).
Playwright mở API 8013/front 5174, MySQL demo riêng; không dùng API/mock response giả.
Đây là bằng chứng kiểm thử local, không phải biên bản UAT hay xác nhận GitHub Actions đã chạy.
