# Tuần 6 — WBS 6.1–6.5

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
  Student chỉ nhận receipt event, không nhận ghi chú review nội bộ.
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

## 6.3 Báo cáo và export CSV

Admin/Instructor cần `course.read` và scope quản lý course (owner/course_staff INSTRUCTOR).
Student dùng API grade/progress cá nhân hiện có. Report course không trả credentials,
đáp án hoặc grading key. Learner totals tính trên toàn bộ bộ lọc, không chỉ trang hiện tại;
course_progress là snapshot lưu gần nhất, không đổi Enrollment.status.

| API | Hành vi |
| --- | --- |
| GET `/api/v1/reports/courses/{id}/learners` | search username, enrollment_status; items/totals/total/limit/offset |
| GET `/api/v1/reports/courses/{id}/gradebook` | search username, grade_status=PUBLISHED (mặc định)/DRAFT/ALL, assessment_type=ASSIGNMENT/EXAM |
| POST `/api/v1/exports` | 202; request_id UUID, kind=OVERVIEW/LEARNERS/GRADEBOOK, course_id cho export course, filters |
| GET `/api/v1/exports` | Danh sách job do người hiện tại tạo, phân trang |
| GET `/api/v1/exports/{id}` | Trạng thái job và row_count; kiểm lại role/permission/scope |
| GET `/api/v1/exports/{id}/content` | Chủ job có quyền hiện tại, READY, private CSV attachment; audit download |

Report/list limit 1–100 và offset ≥0. `OVERVIEW` chỉ dành cho Admin, xuất các course còn
tồn tại theo dashboard tổng quan; không nhận course/filter. Learner export nhận search/
enrollment_status. Gradebook export nhận search/grade_status/assessment_type; mặc định
chỉ điểm Published. Filter không phù hợp loại export bị 422. Retry cùng request_id và
payload trả job cũ; dùng lại ID với payload khác trả 409. Tối đa 3 job PENDING/người.

Migration `0012_export_jobs` lưu queue PENDING → READY/FAILED. Lifespan chạy worker mỗi
2 giây. Worker lấy lại user/role/permission/course scope, dùng lock requester → course →
job; nhiều worker không tạo trùng kết quả. Job chưa commit tiếp tục PENDING khi restart.
Serialize/ghi CSV chạy ngoài event loop; cancellation đợi file đóng, xóa file mới và
rollback job về PENDING để lần chạy tiếp xử lý lại.
CSV là snapshot lúc xử lý, không phải lúc gửi yêu cầu; tối đa 10.000 dòng, vượt giới hạn
trả FAILED/ROW_LIMIT, không cắt dữ liệu âm thầm. FAILED/ACCESS_REVOKED khi quyền thay đổi,
FAILED/EXPORT_FAILED cho lỗi xử lý; có thể tạo yêu cầu mới sau khi xử lý nguyên nhân.

File UTF-8 BOM lưu tại private storage với tên UUID; API không trả filesystem path và
không có URL public. Download không cache, chống MIME sniffing và kiểm quyền lại. CSV
escape dấu phẩy/quote/newline và thêm dấu nháy đơn trước text có thể thành công thức
Excel; số được giữ dạng số. Export request/ready/failed/download có audit; audit lỗi khi
materialize thì rollback và xóa file vừa tạo. Chính sách retention/dọn file nâng cao
thuộc phần vận hành tiếp theo.

UI Admin reports có export tổng quan; UI course manager có bảng tiến độ/gradebook,
bộ lọc, phân trang và export theo bộ lọc. Lịch sử job tự cập nhật khi đang xử lý và có
nút tải CSV, lỗi/empty/loading states. Chỉ chủ job truy cập kết quả, kể cả Admin.

## 6.4 Acceptance checklist và business rules

Checklist [nghiệm thu MVP](../testing/week-6-acceptance.md) ánh xạ business rules sang
test và điều kiện quan sát. `test_week6_acceptance.py` có luồng HTTP xuyên module:
ghi danh → học → submission versions → autosave/resume/submit → công bố điểm →
completion → forum/notifications → report/CSV/audit, cùng ba trường hợp late policy.
Browser tuần 6 kiểm tra nộp text/PDF, autosave/resume, submit và grade visibility/feedback.
Test tìm kiếm tuần 2 chờ catalog tải xong trước khi kiểm số card.

Chạy full backend với `python -m pytest -q --strict-markers --require-mysql`.
Thiếu MYSQL_TEST_ADMIN_URL thì dừng trước collection; CI sử dụng cùng cờ để tránh
integration skip khi nghiệm thu. Test dùng MySQL/storage riêng, không thay database `lms`.

## 6.5 Security tests AuthN/AuthZ, IDOR và file access

Suite `test_week6_access_security.py` có 7 case trên MySQL thật: 15 trường hợp AuthN
bị từ chối, claims quyền không vượt DB grants, matrix 17 thao tác × 3 actor, hai Student
ACTIVE cùng course kiểm IDOR attempt/submission/file/grade/notification, parent scope,
upload cleanup/path containment, account/enrollment/permission/staff revocation và
export requester isolation. Request bị từ chối không thay đổi dữ liệu nghiệp vụ.
Chi tiết [security checklist](../testing/week-6-security.md); chạy riêng bằng
`python -m pytest -q --strict-markers --require-mysql -m security`.

Lesson/submission downloads bổ sung `Cache-Control: no-store` và
`X-Content-Type-Options: nosniff`, thống nhất với private CSV. Giữ backend authorization
trước khi đọc file, kiểm containment tại private storage và không trả location trong metadata.

## Chạy và kiểm chứng

```powershell
# Từ backend
../../.venv/Scripts/python.exe -m alembic upgrade head
../../.venv/Scripts/python.exe -m scripts.run_demo

# Từ frontend ở terminal khác
npm run dev
npm test
npm run build
npm run test:e2e
```

Backend acceptance tuần 6: `tests/integration/test_week6_audit.py`,
`test_week6_security.py`, `test_week6_reports.py`, `test_week6_acceptance.py` và
`test_week6_access_security.py`; cần MYSQL_TEST_ADMIN_URL cho MySQL
disposable test DB. CSV safety: `tests/unit/test_csv_export.py`. Browser acceptance:
`tests/e2e/week6.spec.ts`. Chạy full pytest/Ruff/contracts/sync tests theo hướng dẫn backend.
Database ứng dụng chính `lms` ở head `0012_export_jobs`; migrate bằng upgrade, không import
canonical SQL vào DB đang có dữ liệu. WBS 6.6–6.8 đã hoàn thành; xem runbook release.

## 6.6–6.8 Seed, release candidate và demo MVP

Seed `scripts.run_demo` dựng ba role, khóa `DEMO_WEEK2`, assignment Published và exam Published có câu hỏi.
Seed idempotent và không ghi đè trạng thái học tập; xem [runbook release](../testing/week-6-release.md).

`infrastructure/scripts/release_candidate.py` chạy full regression với MySQL disposable, contract/sync checks,
frontend unit/build và Playwright. Cờ `--skip-e2e` chỉ dành cho vòng lặp local, không dùng làm evidence release.

Checkpoint 15/10/2026: WBS 6.6–6.8 đã hoàn thành; các tiêu chí UAT production/hardening thuộc kế hoạch tuần 7–8.
