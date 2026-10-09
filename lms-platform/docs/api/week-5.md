# Tuần 5 — WBS 5.1–5.6

Ứng dụng tiếp tục dùng **database lms**. API: http://127.0.0.1:8002;
frontend: http://127.0.0.1:5173. Database head hiện tại là migration 0009.

## 5.1 Layout, API client, routing và trạng thái UI

- Shell/sidebar dùng chung, menu theo role, active navigation, skip link và nhãn form.
  Các trang tài khoản/báo cáo/khóa học dùng cùng API client và form chống submit kép.
- Guard cả route con `/admin/users`, `/admin/reports` và query string; Student không
  gọi API admin khi đi link trực tiếp. Backend luôn kiểm role/permission/scope hiện tại.
- Có loading/aria-busy, empty, error/trace ID/retry, forbidden và success;
  generation guard bỏ response cũ khi đổi route. Token chỉ giữ trong bộ nhớ.
- Form và API có validation; lỗi không xóa nội dung form. Phân trang tài khoản,
  report và danh sách course quản lý. Tìm/lọc course áp dụng cho trang hiện tại.

## 5.2 Admin: user/role, course oversight và reports

Routes UI: `#/admin`, `#/admin/users`, `#/admin/reports`.

| API | Hành vi |
| --- | --- |
| GET /api/v1/users | search username/email, status; limit 1–100, offset ≥0; trả items/total/limit/offset |
| POST /api/v1/users | email/username/password/status/roles; roles ADMIN/INSTRUCTOR/STUDENT; audit cùng transaction |
| PUT /api/v1/users/{id} | sửa email/username, giữ password/status/role; 409 khi trùng dữ liệu |
| GET /api/v1/reports/overview | tổng user/course/enrollment/completion; bảng course, phân trang; Admin-only |
| GET /api/v1/dashboard/instructor | số liệu course sở hữu hoặc được phân công INSTRUCTOR; cần course.read |

Tài khoản trả về chỉ gồm id/email/username/status/roles/created_at/updated_at,
không có hash/password/token. Id BIGINT luôn là chuỗi. Các API status và role/permission
tuần 2 được tái sử dụng; khóa tài khoản thu hồi refresh token. UI không cho tự khóa
tài khoản đang dùng hoặc tự gỡ role ADMIN. Đây là biện pháp UX; quyền quyết định ở API.

Báo cáo gồm total_users, active_users, total_courses, published_courses, enrollments,
active_enrollments, completed_learners và dữ liệu từng course (enrollments,
active_enrollments, completed_learners, draft_grades, submissions). Không tính course/user
đã soft delete. Completion là course_progress lưu gần nhất; không đổi Enrollment.status.
Xuất dữ liệu/report nâng cao vẫn thuộc tuần 6.

## 5.3 Instructor dashboard và course/content builder

- `#/instructor` hiển thị tổng lớp phụ trách, học viên đang học, số bài nộp và điểm nháp
  chờ công bố. Course list có tìm/lọc và phân trang.
- Tạo/sửa metadata course, công bố/chuyển Draft/lưu trữ/xóa Draft; sửa course ở Draft.
- Tạo/sửa/xóa chương và bài học, chọn ARTICLE/VIDEO/DOCUMENT/LIVE, preview,
  nội dung, sắp xếp lên/xuống bằng full sibling ID list.
- Tài nguyên LINK/FILE dùng upload validation và private download backend có sẵn.
- Builder cấu hình cả rule lesson/submission lẫn grade assignment/exam Published
  và ngưỡng điểm. Không vô tình xóa gate mới khi lưu rule.
- UI Published/Archived không hiển thị editor; backend chặn chỉnh sửa ngoài scope/Draft.
  Xóa qua bước xác nhận tại chỗ; lịch sử/soft delete giữ bởi nghiệp vụ hiện tại.

## Chạy và demo

```powershell
# Từ backend; migration/seed ba role trên lms
../../.venv/Scripts/python.exe -m scripts.run_demo

# Từ frontend, ở terminal khác
npm run dev
npm run seed:demo
node scripts/check-week5.mjs
```

Seed bổ sung 8 course SHOWCASE_* với ba chương/sáu bài, assignment, enrollment và
progress. `scripts/seed-showcase.mjs` mặc định gọi API 8002; tùy chọn LMS_API_BASE
cho API localhost khác. Tài khoản demo_admin/demo_instructor/demo_student và mật khẩu
demo trong seed_week2.py. Seed giữ dữ liệu hiện có; smoke check không ghi nghiệp vụ.

## 5.4 Student portal, 5.5 assessment UI và 5.6 notification

- Student dashboard hiển thị khóa học đã ghi danh, trạng thái và phần trăm tiến độ; trang khóa học có lesson player, tài nguyên riêng tư và nút cập nhật completion.
- Student có thể xem assignment, nộp text/file và lịch sử version; làm exam với eligibility, timer server, autosave, resume và submit; chỉ xem grade đã Published.
- Notification in-app lưu theo người nhận, có danh sách phân trang, unread count, đánh dấu từng thông báo hoặc tất cả đã đọc. Các event enrollment, assignment submission và grade publication tạo thông báo trong cùng transaction.

API notification:

| Method | Path | Mô tả |
| --- | --- | --- |
| GET | `/api/v1/notifications` | Danh sách, `limit`, `offset`, `unread_only` |
| GET | `/api/v1/notifications/unread-count` | Số thông báo chưa đọc |
| PATCH | `/api/v1/notifications/{id}/read` | Đánh dấu đã đọc, chỉ chủ sở hữu |
| POST | `/api/v1/notifications/read-all` | Đánh dấu toàn bộ đã đọc |

Migration `0009_notifications` bổ sung bảng thông báo trên database `lms`.

### 5.7 Forum/discussion trong course

Forum được tạo theo từng course và dùng cùng scope `course.read`: Admin/Instructor có
quyền quản lý course, Student cần enrollment ACTIVE trong course PUBLISHED. API hỗ trợ
đọc forum, phân trang thread, tạo thread, xem chi tiết và gửi reply:

| Method | Path | Mô tả |
| --- | --- | --- |
| GET | `/api/v1/courses/{course_id}/forum` | Thông tin forum của course |
| GET | `/api/v1/courses/{course_id}/forum/threads` | Danh sách thread, `limit`, `offset` |
| POST | `/api/v1/courses/{course_id}/forum/threads` | Tạo thread với `title`, `body` |
| GET | `/api/v1/courses/{course_id}/forum/threads/{thread_id}` | Thread và các reply |
| POST | `/api/v1/courses/{course_id}/forum/threads/{thread_id}/messages` | Gửi reply với `body` |

Migration `0010_forum_messaging` tạo các bảng `forums`, `threads`, `messages`; bài viết
không bị lộ giữa các course và thread LOCKED/ARCHIVED được xử lý theo trạng thái.

## Phạm vi tiếp theo

Phạm vi tiếp theo còn lại là WBS 5.8: nghiệm thu responsive/a11y toàn bộ. UI Student,
assignment/exam/grade, notification và forum/discussion đã có ở trên.
UI Student nền tảng từ tuần 2/3 vẫn được regression, không đánh dấu những task này.
