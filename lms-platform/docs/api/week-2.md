# API tuần 2 — task 2.1–2.4

Prefix `/api/v1`; success/error envelope và `trace_id` theo shared contracts.
OpenAPI đầy đủ tại `shared/contracts/openapi.json`. Các ID trả về là chuỗi thập phân.
Ngày kiểm chứng: 17/09/2026. Không cần migration mới ngoài `0001_p0`.

## Đăng nhập và phiên

- `POST /auth/login`: `{login, password}` → access_token, refresh_token,
  expires_in (giây), refresh_expires_in (giây), token_type=bearer.
- `POST /auth/refresh`: `{refresh_token}` → cặp token mới. Token cũ chỉ dùng một lần.
- `POST /auth/logout`: `{refresh_token}` → `{logged_out: true}`; thu hồi cả family.
  Gọi lại logout với token đã biết vẫn thành công. Token không tồn tại trả 401.
- `GET /auth/me`: profile và role hiện tại; cần Bearer access token.
- `PATCH /auth/users/{id}/status`: Admin gửi `{status: ACTIVE|INACTIVE|LOCKED}`.
  Khóa/ngừng kích hoạt tài khoản cũng thu hồi mọi refresh token của tài khoản đó.

Refresh token là chuỗi ngẫu nhiên 384 bit, DB chỉ lưu SHA-256. Mặc định access token
hết hạn sau 15 phút, refresh token sau 30 ngày kể từ lần cấp; cấu hình qua environment.
Token response có `Cache-Control: no-store`. Refresh hết hạn, account không hoạt động
hoặc token đã dùng đều bị từ chối 401; reuse thu hồi cả family, kể cả token mới nhất.
Các thao tác login/rotation/logout được tuần tự hóa bằng khóa hàng user trong transaction.
Logout thu hồi refresh session; access token đã phát vẫn có thể dùng tới khi hết hạn.
Role/account hiện tại vẫn được kiểm tra ở mỗi request bằng SQL.

## Quyền và phạm vi

Các API quản trị sau yêu cầu role ADMIN, không cần permission khóa học để bootstrap:

- `GET /roles`, `GET /permissions`: danh mục role có sẵn và permission hỗ trợ.
- `GET /users/{id}/roles`, `PUT|DELETE /users/{id}/roles/{role_code}`.
- `GET /roles/{role_code}/permissions`.
- `PUT|DELETE /roles/{role_code}/permissions/{permission}`: cấp/thu hồi idempotent.

Catalog permission: `course.read`, `course.write`, `course.publish`.
Admin cấp các permission cần thiết cho ADMIN/INSTRUCTOR qua API trên trước khi sử dụng
course API; không tự động coi role ADMIN là có mọi permission. STUDENT cần `course.read`
để xem nội dung đã ghi danh. Seed/demo ba role vẫn thuộc task 2.7.

Course write/publish cần đồng thời role ADMIN hoặc INSTRUCTOR và permission tương ứng.
Admin quản lý mọi khóa học. Instructor chỉ quản lý khóa mình tạo hoặc được gán trong
`course_staff` với role INSTRUCTOR. ASSISTANT không có quyền sửa khóa học.
Các tài khoản khác chỉ đọc khóa PUBLISHED có enrollment ACTIVE của chính mình.
Course list lọc theo cùng phạm vi. Thiếu quyền/sai phạm vi trả 403; tài nguyên không
tồn tại hoặc đã xóa mềm trả 404. Đổi role/permission có hiệu lực từ request tiếp theo.
API tạo/sửa enrollment và course_staff thuộc task 2.5; ở đây kiểm tra scope trên dữ liệu hiện có.

## Khóa học

| Method/path | Nội dung |
|---|---|
| POST /courses | `{code, title, description?}` → khóa DRAFT, 201 |
| GET /courses | `limit=1..100`, `offset>=0`, `status?`; danh sách trong phạm vi |
| GET /courses/{id} | Chi tiết khóa học |
| PUT /courses/{id} | Thay metadata bằng `{code, title, description?}` |
| DELETE /courses/{id} | Xóa mềm khóa DRAFT |
| POST /courses/{id}/status | `{status: PUBLISHED|DRAFT|ARCHIVED}` |

`code` dài 1–64, gồm chữ/số/gạch ngang/gạch dưới; unique không phân biệt hoa thường
theo collation MySQL. Trùng code trả 409. Title sau trim phải dài 1–255.
Không cho truyền `created_by` hoặc `status` trong body CRUD; owner lấy từ tài khoản hiện tại.

Transition: DRAFT → PUBLISHED; PUBLISHED → DRAFT hoặc ARCHIVED; ARCHIVED → DRAFT.
Mọi transition khác trả 409. Công bố cần ít nhất một module, mỗi module có ít nhất
một lesson, mọi lesson có content không rỗng. Với VIDEO/DOCUMENT/LIVE, content là metadata
hoặc đường dẫn nội dung; upload/kiểm chứng tệp thực tế thuộc phần quản lý tệp sau này.
Metadata, cấu trúc, ordering và xóa chỉ sửa ở DRAFT. Đưa khóa về DRAFT trước khi sửa.
Course lock và locking reads giữ kiểm tra publish nhất quán với các cập nhật đồng thời.

## Module và lesson

Base `/courses/{course_id}/modules`:

| Method/path | Nội dung |
|---|---|
| GET base | Toàn bộ module/lesson đang hoạt động, theo position |
| POST base | `{title}`; thêm cuối danh sách, trả `{id}`, 201 |
| PUT base/order | `{ids: [id, ...]}` theo thứ tự module mong muốn |
| PUT base/{module_id} | `{title}` |
| DELETE base/{module_id} | Xóa mềm module; lesson con không còn đọc được |
| POST base/{module_id}/lessons | `{title, lesson_type, content?, is_preview?}`, 201 |
| PUT base/{module_id}/lessons/order | `{ids: [id, ...]}` theo thứ tự lesson mong muốn |
| GET base/{module_id}/lessons/{lesson_id} | Chi tiết lesson |
| PUT base/{module_id}/lessons/{lesson_id} | Thay metadata lesson |
| DELETE base/{module_id}/lessons/{lesson_id} | Xóa mềm lesson |

Lesson type: VIDEO/ARTICLE/DOCUMENT/LIVE. `is_preview` chỉ là metadata trong task này,
không mở truy cập ẩn danh. GET curriculum trả đủ metadata để đọc từng module.
Body order phải chứa đúng toàn bộ ID sibling còn hoạt động, không lặp, không khác parent;
vi phạm trả 422. Có thể gửi ID dạng chuỗi để giữ độ chính xác BIGINT từ JavaScript.
Reorder chạy trong một transaction, tránh xung đột UNIQUE kể cả khi swap hoặc có hàng
đã xóa mềm. Child ID phải thuộc đúng module/course trong URL, nếu không trả 404.

Mọi thay đổi course/content/role/permission/account có audit cùng transaction;
nếu ghi audit thất bại thì business write rollback. Token không được ghi vào audit/log.

## Kiểm chứng

`tests/integration/test_week2_mysql.py` tạo database ngẫu nhiên `lms_test_*`, migrate,
seed dữ liệu kiểm thử riêng rồi chạy HTTP với SQL thật. Test không sửa database `lms`.
Chạy bằng `MYSQL_TEST_ADMIN_URL` có quyền tạo/xóa database thử nghiệm:

```powershell
.venv/Scripts/python -m pytest lms-platform/backend/tests -q
.venv/Scripts/python -m ruff check lms-platform/backend/src lms-platform/backend/tests lms-platform/database/migrations
.venv/Scripts/python lms-platform/backend/scripts/export_contracts.py --check
```
