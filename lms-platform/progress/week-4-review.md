# Checkpoint 01/10/2026 — WBS 4.1–4.4

Đã hoàn thành 4 nhóm tiêu chí cho mỗi task: schema/migration, API theo phạm vi,
acceptance trên MySQL thật và tài liệu vận hành (`docs/api/week-4.md`).

- **4.1:** bank/category/question API; difficulty và lọc; blueprint theo bank/category/
  difficulty/type/count/points; publish thiếu câu trả 409 và rollback. FK và kiểm tra
  application chặn tham chiếu category/bank/course khác.
- **4.2:** create/list/detail/update/delete exam Draft; publish khóa trạng thái; ownership,
  staff và permission; eligibility theo course Published/enrollment Active/cửa sổ/
  attempt limit. Manager thao tác assessment trên course Published được.
- **4.3:** một attempt đang làm; start đồng thời chỉ một request thành công; timer MySQL
  UTC, deadline không kéo dài khi resume, snapshot câu hỏi riêng. Submit idempotent và
  chuyển AUTO_SUBMITTED khi hết hạn được phát hiện qua request tiếp theo.
- **4.4:** autosave JSON; version chống ghi đè cũ; validate option thuộc đề; resume trả
  đáp án/version/thời gian còn lại và tuân thủ allow_resume. Thu hồi enrollment chặn
  resume/save/submit. Không trả answer key/score chưa công bố cho Student.

Kiểm chứng:

- Full backend: **75 passed**, không skip, trên MySQL thật.
- Sau đó bổ sung hai scenario, chạy lại toàn bộ suite riêng tuần 4: **6 passed**
  (CRUD/blueprint; autosave/timer; concurrency/suspension; resume policy; validation/
  snapshot; future window/audit rollback). Tổng cộng 77 test backend khác nhau đã đạt.
- Migration upgrade → downgrade → upgrade và import snapshot `lms.sql` vào database
  tạm: **1 passed**; so sánh toàn bộ column/type/nullability với schema Alembic.
- Ruff toàn backend/scripts/tests/migrations và OpenAPI contract drift: đạt.
- Database ứng dụng **lms** đã nâng lên **0006_exam_policy (head)**; prepare/seed chạy
  thành công trên lms. Demo mặc định dùng lms. Test DROP schema chỉ dùng lms_test_* tạm.

Checkpoint này không bao gồm auto-grading/grade publish, giao diện thi hoặc worker
quét deadline nền. Chỉ cập nhật WBS 4.1–4.4, không đánh dấu toàn bộ tuần 4 hoàn tất.
Các database demo cũ không bị xóa hay tự trộn dữ liệu vào lms.

Đính chính: bản đầu đã sync 100% trước khi API đầy đủ và trước acceptance. Tiến độ đã
được trả về Đang thực hiện; chỉ đưa lại 100% sau khi hoàn thành và kiểm chứng các mục trên.
