# Review tuần 6 — 12/10/2026

## WBS 6.1 — hoàn thành

- Publish course/assignment/exam, role/permission, grade draft/publish/revise,
  assignment text/file và exam submit/auto-submit ghi audit trong transaction nghiệp vụ.
- Audit chứa actor/resource/trace/timestamp và ngữ cảnh phiên bản/trạng thái/điểm;
  không ghi credentials hoặc nội dung bài nộp. Grade history giữ snapshot các version.
- Admin có API/trang nhật ký với filter và pagination; Student/Instructor không truy cập.
- 25 MySQL tests audit/assignment/grading/portal đạt, gồm rollback publish/permission/role,
  submission, grade publication và exam grading khi audit lỗi. Browser acceptance Admin
  lọc log, empty state và Student guard đạt. Frontend build, Ruff và export contracts đạt.

## WBS 6.2 — hoàn thành

- Security login thành công/thất bại/unknown/locked, account lock, token revoke/reuse và
  denial 401/403 được lưu; Admin có filter/pagination. Không ghi body/query/credentials.
- Migration 0011, event TAB_HIDDEN/WINDOW_BLUR dùng UUID retry và thời gian server,
  giới hạn 200/attempt, kiểm scope/time/enrollment. UI dừng timer/listener khi rời trang.
- Manager course xem/review PENDING, ghi note/reviewer/time/version và audit cùng transaction.
  Event/review không thay đổi điểm; kiểm chứng bài đúng vẫn đạt 10/10 sau review.
- 3 MySQL security acceptance tests đạt, gồm concurrent retry, cross-role, validation,
  review stale version, rollback và event cap. Auth/unit regression đạt; canonical schema
  import/upgrade/downgrade/upgrade đạt. 2 browser acceptance (audit/security/telemetry/review)
  đạt, frontend build và Ruff đạt.

## WBS 6.3 — hoàn thành

- Manager course có report học viên và gradebook; filter/pagination và aggregates toàn
  bộ bộ lọc; Published là mặc định, Draft chỉ dành cho manager. Admin có export overview.
- Migration 0012, durable queue với request UUID, pending cap, worker background và
  snapshot CSV; kết quả private chỉ chủ job có scope/permission hiện tại được tải.
- UTF-8 BOM, CSV quoting/formula protection, limit 10.000 dòng rõ ràng; audit request/
  ready/failed/download. Audit failure rollback và xóa file mới; scope revoked gây FAILED
  hoặc chặn download. Worker concurrency không tạo trùng file/audit.
- 6 MySQL report/export tests và CSV safety test đạt: totals/filter/page/default Published,
  scope/staff, queue retry/concurrent worker, private content, permission revocation,
  audit failure/cleanup, row limit và grade revision trong lúc chờ course lock.
  Serialization không chặn API; cancellation đóng/xóa file trước rollback và restart job.
- 3 browser journeys đạt: audit/security, telemetry/review và report filters → CSV gradebook
  cùng CSV overview.

## Kiểm chứng cuối

- Full backend regression: **107 passed**, không skip; sau thay đổi serialization, toàn bộ
  **6 report/export tests passed**, gồm test cancellation/restart mới bổ sung.
- Frontend: **11 unit tests passed**, build đạt. **11 browser scenarios đạt**: 10 đạt khi
  chạy toàn bộ, case mobile còn lại đạt khi chạy lại sau sửa kiểm tra nhận diện nhãn HTML
  implicit label (không bỏ kiểm tra controls chưa có tên).
- **5 progress sync tests passed**, Ruff toàn backend/scripts/migrations và contract drift đạt.
- Database chính `lms` đã upgrade và xác nhận `0012_export_jobs (head)`.
- Preview Sheet khớp đúng ba task; apply và đọc lại xác nhận **6.1, 6.2, 6.3 = 100%**.
  Chỉ F/G của ba task được ghi; giữ nguyên công thức/layout/owner/deadline và task khác.

Chi tiết contract: [docs/api/week-6.md](../docs/api/week-6.md).
Chỉ cập nhật WBS 6.1–6.3 khi có bằng chứng cho từng mục; không đánh dấu 6.4–6.8.
