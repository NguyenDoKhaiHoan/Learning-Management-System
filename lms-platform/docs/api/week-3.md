# API tuần 3 — learning content, assignment và progress (WBS 3.1–3.8)

## Phạm vi

- File lesson được lưu trong kho private, không trả storage key cho client.
- Upload dùng raw request body, `Content-Type` và header `X-File-Name`; mặc định tối đa 25 MiB.
- MIME cho phép: PDF, JPEG, PNG, UTF-8 text và MP4. API kiểm cả MIME khai báo lẫn chữ ký/nội dung file.
- Student chỉ đọc lesson/resource và cập nhật progress khi course `PUBLISHED` và enrollment `ACTIVE`.
- Progress chỉ đi tới: `NOT_STARTED -> IN_PROGRESS -> COMPLETED`; vị trí xem cũng không được giảm.
- Course progress được tính lại trong cùng transaction với lesson progress.

## Resource API

Base path:
`/api/v1/courses/{course_id}/modules/{module_id}/lessons/{lesson_id}/resources`

| Method | Path | Quyền / chức năng |
|---|---|---|
| `GET` | base | Người quản lý course hoặc Student đủ điều kiện; liệt kê metadata |
| `POST` | base | `course.write`, course Draft; tạo link HTTP(S) |
| `POST` | `base/file` | `course.write`, course Draft; upload file private |
| `GET` | `base/{resource_id}/content` | Đọc file sau khi kiểm tra lại quyền course/enrollment |
| `DELETE` | `base/{resource_id}` | `course.write`, course Draft; soft-delete metadata |

Ví dụ upload:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "$api/api/v1/courses/1/modules/1/lessons/1/resources/file" `
  -Headers @{ Authorization="Bearer $token"; "X-File-Name"="lecture.pdf" } `
  -ContentType "application/pdf" -InFile .\lecture.pdf
```

Response metadata có `title`, `resource_type`, `mime_type`, `size_bytes`, `sha256` và
`uploaded_by`; không chứa đường dẫn vật lý hay object key.

## Completion và progress API

| Method | Path | Chức năng |
|---|---|---|
| `GET` | `/courses/{course_id}/completion-rule` | Đọc rule; mặc định 100% lesson |
| `PUT` | `/courses/{course_id}/completion-rule` | Manager đặt phần trăm; chỉ Course Draft |
| `GET` | `/courses/{course_id}/progress/me` | Student đọc tổng hợp của enrollment hiện tại |
| `PUT` | `/courses/{course_id}/lessons/{lesson_id}/progress` | Student cập nhật trạng thái/vị trí |

Payload cập nhật lesson:

```json
{
  "status": "IN_PROGRESS",
  "last_position_seconds": 120
}
```

`COMPLETED` là trạng thái cuối. Request lùi trạng thái hoặc giảm
`last_position_seconds` trả `409`. IDOR qua course/lesson/resource khác trả `404` sau
khi resource boundary hợp lệ; thiếu quyền course/enrollment trả `403`.

## Schema và vận hành

Migration `0002_week3_learning`:

- bổ sung `sha256`, `uploaded_by` cho `lesson_resources`;
- tạo `completion_rules`, `lesson_progress`, `course_progress`;
- dùng FK, unique key, check constraint, InnoDB và `utf8mb4_unicode_ci`.

Cấu hình:

```dotenv
PRIVATE_STORAGE_ROOT=../storage/private
MAX_UPLOAD_BYTES=26214400
```

Chạy migration và kiểm tra contract:

```powershell
alembic upgrade head
python scripts/export_contracts.py --check
```

## Assignment, submission và completion (3.4–3.8)

Base: `/api/v1/courses/{course_id}/assignments`.

| Method | Path | Chức năng |
|---|---|---|
| GET/POST | base | List/tạo assignment |
| GET/PUT/DELETE | `base/{assignment_id}` | Chi tiết/sửa/xóa nháp |
| POST | `base/{assignment_id}/status` | PUBLISHED → CLOSED → ARCHIVED |
| POST | `base/{assignment_id}/submissions` | Student nộp answer_text |
| POST | `base/{assignment_id}/submissions/file` | Student nộp file raw body |
| GET | `base/{assignment_id}/submissions/mine` | Lịch sử nộp của mình |
| GET | `base/{assignment_id}/submissions` | Manager xem bài nộp |
| GET | `base/{assignment_id}/submissions/{submission_id}/files` | Metadata file |
| GET | `base/{assignment_id}/submissions/{submission_id}/files/{file_id}/content` | File private |

Assignment nhận title/description, opens_at/due_at có timezone, allow_late/late_until,
max_attempts, max_file_bytes, allowed_mime_types và max_score. Chỉ sửa/xóa khi DRAFT;
không quản lý nội dung course Archived. Student chỉ đọc Published/Closed và chỉ nộp
trong cửa sổ cho phép; late_until giới hạn nộp trễ khi allow_late=true.
Mỗi lần nộp tạo version mới bất biến, lưu student/submitted_at/SUBMITTED hoặc LATE;
các request đồng thời không vượt max_attempts. File theo cùng validation/kho private
như lesson; manager của course và chủ bài nộp mới được tải.

Completion rule nhận thêm `require_submitted_assignments`. Khi bật, hoàn thành khóa
đòi đủ tỷ lệ lesson cấu hình và đã nộp tất cả assignment Published/Closed.
Tỷ lệ progress tổng hợp lesson và assignment; trạng thái completion tính theo tỷ lệ
thật, không dựa vào phần trăm hiển thị đã làm tròn. Nộp bài cập nhật course_progress
cùng transaction/audit. Rule này chưa dùng grade hoặc exam (WBS 4.7).

Demo có thể chạy lại với MySQL tạm và MYSQL_TEST_ADMIN_URL, từ backend:

```powershell
python -m pytest tests/integration/test_week3_assignments.py -v
python -m pytest tests/integration/test_week3_assignments.py::test_completion_rule_requires_published_assignment_submission -v
```

Demo thứ hai tạo lesson/assignment, bật rule cần nộp bài, publish/ghi danh Active,
Student hoàn thành lesson (progress 50%, chưa complete), nộp bài (100%, có completed_at).
Frontend hiện có học lesson/đánh dấu hoàn thành, assignment CRUD, nộp text/file và xem
lịch sử bài nộp; luồng nghiệp vụ bên trên được kiểm chứng qua HTTP trên MySQL thật.
