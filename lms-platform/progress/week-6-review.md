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

Chi tiết contract: [docs/api/week-6.md](../docs/api/week-6.md).
Chỉ cập nhật WBS 6.1–6.3 khi có bằng chứng cho từng mục; không đánh dấu 6.4–6.8.
