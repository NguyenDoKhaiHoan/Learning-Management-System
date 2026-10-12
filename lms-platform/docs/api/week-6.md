# Tuần 6 — WBS 6.1–6.3

## 6.1 Audit trail

Các thay đổi course/assignment/exam publication, role/permission, grade draft/publish/revise,
assignment submission và exam submit/auto-submit ghi audit cùng transaction nghiệp vụ.
Audit lỗi thì thay đổi nghiệp vụ rollback. Grade history giữ snapshot từng version;
audit grade chứa score/max_score/status/version và reason điều chỉnh. Submission audit
chứa course/enrollment/assignment/version/type; không lưu nội dung bài hoặc credentials.

`GET /api/v1/audit/logs` chỉ dành cho Admin. Có filter actor_id/action/resource/resource_id/
trace_id/since/until, limit 1–100 và offset ≥0; trả items/total/limit/offset. ID là chuỗi,
sắp xếp timestamp/id giảm dần. Thời gian không có timezone hiểu là UTC. Không có API sửa/xóa log.
UI `#/admin/audit` hỗ trợ lọc và phân trang, route guard cùng backend authorization.

Kiểm chứng: `tests/integration/test_week6_audit.py` và regression tuần 3/4/5.

## 6.2 Security events và review flag

Login thành công/thất bại (kể cả username không tồn tại/tài khoản khóa), khóa tài khoản,
token revoke/reuse và HTTP 401/403 được ghi nhận. Denial ghi metadata trong transaction
riêng để không mất log khi nghiệp vụ rollback. Không lưu token/password/body/query string;
IP lấy từ kết nối trực tiếp, không tin X-Forwarded-For. Khi database lỗi, denial vẫn giữ
401/403 và báo lỗi persistence trong log hệ thống.

- `GET /api/v1/audit/security-events`: Admin; filter event_type/severity/actor_id/trace_id,
  limit/offset. UI `#/admin/security`.
- `POST /api/v1/attempts/{id}/events`: Student sở hữu attempt đang chạy, enrollment ACTIVE,
  course/exam Published. Body `{client_event_id: UUID, event_type: TAB_HIDDEN|WINDOW_BLUR}`.
  Timestamp do server ghi. Retry cùng ID/type trả event cũ; cùng ID khác type trả 409.
  Tối đa 200 event/attempt; không nhận payload tùy ý hoặc key đáp án.
- `GET /api/v1/courses/{id}/attempt-events`: Admin/Instructor có course.write và scope course,
  filter status=PENDING|REVIEWED|DISMISSED; phân trang.
- `PATCH /api/v1/courses/{id}/attempt-events/{event_id}/review`: expected_version,
  status=REVIEWED|DISMISSED, note bắt buộc (1–1000 ký tự). Chỉ review PENDING một lần,
  ghi reviewer/time/version và audit `security.review` cùng transaction.

Migration `0011_attempt_events` lưu event/cờ review. Student UI ghi sự kiện đổi tab/mất
focus, gộp burst trong 1 giây và retry một lần cùng UUID; dừng listener/timer khi nộp hoặc
rời trang. UI course cho manager có danh sách và form review. Event là dấu hiệu từ client,
không chứng minh gian lận, không tự thay điểm hoặc khóa lượt thi. Proctoring/risk scoring
nâng cao vẫn thuộc backlog.
