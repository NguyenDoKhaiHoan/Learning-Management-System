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
Checkpoint 12/10 chỉ cập nhật WBS 6.1–6.3; các mục tiếp theo được xác minh riêng bên dưới.

## WBS 6.4 — hoàn thành, checkpoint 14/10/2026

- Checklist tại `docs/testing/week-6-acceptance.md` đối chiếu business rules với kết
  quả quan sát và các test regression; không suy hoàn thành từ sự hiện diện của file.
- **4 MySQL acceptance cases mới đạt**: luồng ghi danh/học/submission versions/exam/
  grade publication/completion/forum/notifications/report/CSV/audit và ba late policy cases.
  Luồng ghi danh đi qua API; lesson hoàn thành không vượt các assessment gate.
- Browser bổ sung nộp text/PDF thành hai phiên bản, autosave/resume giữ đáp án và timer,
  submit, Draft ẩn và Published hiển thị đúng điểm/feedback. Sửa race trong test tìm kiếm
  tuần 2 bằng cách chờ catalog render trước khi lấy số card.
- **12/12 browser E2E đạt trong một lần chạy full**, **11 frontend unit tests đạt**,
  frontend build, Ruff và contract drift đạt. Full backend MySQL regression đạt,
  không skip; guard `--require-mysql` được kiểm chứng từ chối chạy khi thiếu URL.
- CI chạy strict markers + required MySQL. Database kiểm thử `lms_test_<uuid>` và
  storage tạm; browser dùng `lms_demo_e2e`; không sửa schema/database chính.
- Sheet preview chỉ thay F/G của WBS 6.4; apply và đọc lại xác nhận **6.4 = 100%**.

WBS 6.5–6.8 chưa đánh dấu tại checkpoint này.

## WBS 6.5 — hoàn thành, checkpoint 14/10/2026

- **7 security cases mới đạt** trên MySQL thật: 15 AuthN rejections và claims role
  không vượt DB grants; 51 request AuthZ bị từ chối, không phát sinh thay đổi nghiệp vụ.
- Hai Student cùng enrollment ACTIVE kiểm chứng attempt read/save/submit/events,
  submission metadata/file ID swap, grade visibility và notification recipient isolation.
- Lesson/file parent mismatch, MIME/empty/size và cleanup, path containment, suspension,
  course Draft/account lock và quyền tải lại; export chỉ requester, Admin không vượt
  ownership, thu hồi permission/course_staff chặn kết quả đã READY.
- Test phát hiện lesson/submission downloads thiếu chống cache/MIME sniffing;
  bổ sung `Cache-Control: no-store` và `X-Content-Type-Options: nosniff` cho cả hai route.
  CSV đã có header tương ứng. Chi tiết `docs/testing/week-6-security.md`.

## Kiểm chứng WBS 6.4–6.5 — 14/10/2026

- **119 backend tests passed**, không skip, full suite trên MySQL thật (401 giây).
  Bao gồm migration/canonical schema round-trip, regression các tuần trước và 11 case mới.
- **12/12 browser E2E passed** trong một lượt full sau khi bổ sung case assignment/
  autosave/resume/submit/grade UI; **11 frontend unit tests passed** và build đạt.
- Ruff toàn src/tests/scripts/migrations, contracts drift và **5 progress sync tests đạt**.
  `--require-mysql` trả lỗi trước collection khi thiếu MYSQL_TEST_ADMIN_URL.
- Sheet đồng bộ riêng từng WBS qua preview/apply/readback: **6.4, 6.5 = 100%**.
  Chỉ F/G hai task thay đổi; không thay owner/deadline/tên/công thức/layout/task khác.
- Không cần migration mới; database chính vẫn `0012_export_jobs`. Kiểm thử dùng database
  `lms_test_<uuid>`/storage tạm và browser `lms_demo_e2e`.

WBS 6.6–6.8 chưa thực hiện trong phạm vi này.
