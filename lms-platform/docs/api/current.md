# API hiện hành — checkpoint tuần 8

## Quy ước chung

API đặt dưới `/api/v1`. Thành công trả `{data, trace_id}`; lỗi trả mã HTTP cùng
`code`, `message`, `details` và `trace_id`. Client dùng `X-Trace-ID` để đối chiếu log.
Các response riêng tư (token, file, CSV) có `Cache-Control: no-store`; download file
có `X-Content-Type-Options: nosniff`.

## Nhóm endpoint

| Nhóm | Prefix | Quyền chính |
| --- | --- | --- |
| Identity | `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me` | Public login; các endpoint còn lại cần token |
| User/role | `/users`, `/roles`, `/permissions` | Admin; thay đổi quyền ghi audit |
| Course/content | `/courses`, `/courses/{id}/modules`, `/lessons`, `/resources` | Admin hoặc instructor được scope |
| Enrollment | `/courses/{id}/enrollments` | Student request; instructor/admin duyệt và tạm ngưng |
| Learning | `/lessons/{id}/progress`, `/courses/{id}/progress` | Student có enrollment ACTIVE |
| Assessment | `/assignments`, `/submissions`, `/exams`, `/attempts` | Instructor quản lý; student chỉ thao tác attempt của mình |
| Gradebook | `/courses/{id}/grades`, `/grades/{id}/publish` | Instructor/admin; student chỉ đọc grade Published của mình |
| Communication | `/courses/{id}/forum`, `/notifications` | Thành viên course theo scope; moderation thuộc staff |
| Reports/export | `/reports`, `/exports` | Manager scope; download kiểm tra lại quyền live |
| Operations | `/livez`, `/healthz`, `/metrics` | Health public; metrics bật theo cấu hình |

OpenAPI chỉ mở ở development/test. Contract TypeScript/JSON Schema dùng chung nằm
trong `shared/contracts`; chạy `backend/scripts/export_contracts.py --check` để phát
hiện drift.

## Transaction và idempotency

Enrollment, submission, attempt, grade publish và event notification commit trong một
transaction. Submit assignment/exam và webhook/job dùng request hoặc idempotency key;
retry cùng key không tạo bản ghi nghiệp vụ thứ hai. Worker export/email retry hữu hạn
và chuyển FAILED sau khi hết attempt.
