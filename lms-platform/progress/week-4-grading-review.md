# Checkpoint 02/10/2026 — WBS 4.5–4.6 và regression phần trước

## 4.5 Submit/auto-submit idempotent và auto-grading

- Submit, expiry từ HTTP và worker dùng chung AttemptGrader; trạng thái, điểm, items,
  history và audit commit trong cùng transaction.
- API lifespan chạy worker mỗi 5 giây; quét deadline theo MySQL UTC, không cần request
  của Student. Worker vẫn chấm bài đã lưu khi enrollment bị suspended.
- SINGLE/MULTIPLE/TRUE_FALSE chấm theo tập option đúng trong snapshot; sai/thừa/thiếu/
  bỏ trống = 0. Decimal và input 2 chữ số thập phân giữ đúng điểm 0.1 + 0.2 = 0.3.
- Submit/worker đồng thời không tăng version hay tạo grade/history/audit trùng; late save
  bị từ chối. Lỗi audit rollback cả trạng thái nộp và chấm, retry worker thành công.
- Grade tự động lấy lần thi có điểm cao nhất khi còn nháp tự động; Instructor đã sửa
  hoặc đã publish thì điểm không bị lần thi sau ghi đè.

## 4.6 Grade items, draft/publish/revise, feedback và history

- GradeRepository/GradeService và 8 API quản lý/Student, migration 0007_grading tạo
  grade_items/grade_history và bổ sung feedback/version/source/graded_at.
- Items có key duy nhất, giới hạn score/max_score, tổng maximum khớp assessment;
  tạo manual grade phải có source submission/attempt đúng course/enrollment.
- Sửa DRAFT; publish; revise PUBLISHED cần reason và trở về DRAFT để công bố lại.
  Optimistic version trả 409 cho sửa đồng thời/cũ; retry publish không thêm history.
- Feedback tổng và từng item; mỗi thay đổi lưu snapshot đầy đủ, actor/reason/time và audit.
  Không có API thay đổi/xóa history. Student không xem draft/history/điểm của người khác.
- Live role/permission, owner/course_staff, course/enrollment scope và publication gate.
  Locking reads ngăn grade cũ bị lộ sau khi revise trong lúc request chờ khóa.

## Kiểm chứng

- Full backend: **87 passed**, không skip, trên MySQL 8.0.45 thật; bao gồm upgrade →
  downgrade → upgrade và import canonical lms.sql/so sánh column/type/nullability.
- Sau rà soát transaction, suite tuần 4 chạy lại: **17 passed**. Thêm kiểm thử
  Student đọc grade đang revise: **1 passed**. Tổng **89 test backend khác nhau** đã đạt,
  trong đó 18 scenario tuần 4, 12 scenario grading. Không tuyên bố full run 89 local.
- Test bổ sung chứng minh submit đọc đáp án vừa commit sau authentication/chờ khóa;
  Student không đọc điểm Published từ snapshot cũ khi grade đã quay lại Draft.
- Frontend: **11 unit passed**, build đạt, **3 Playwright E2E passed** cho publish,
  enrollment/suspension, ba role, route guard, desktop/mobile và login lỗi.
- Ruff backend/scripts/tests/migrations, contract drift và **5 progress sync tests** đạt.
- Tài liệu API tuần 4, demo acceptance và schema/OpenAPI cập nhật.

MySQL80 trên máy đang stopped và tài khoản phiên làm việc không có quyền start service.
Kiểm thử dùng server MySQL riêng trên 127.0.0.1:3307, datadir dưới .local-logs (Git ignored),
mọi acceptance database dùng lms_test_* và tự dọn. E2E dùng lms_demo_e2e riêng.
Database ứng dụng lms trên port 3306 chưa áp dụng migration 0007; khi MySQL80 hoạt động,
chạy `python -m alembic upgrade head` tại backend trước khi chạy API phiên bản mới.

## Rà soát phần trước và sheet

- WBS 1.1–1.15, 2.1–2.8, 3.1–3.3, 4.1–4.4 giữ 100% sau regression.
- WBS 3.4–3.8 đã có implementation và MySQL acceptance nhưng thiếu trong tasks.json.
  Bổ sung bằng chứng/verified_at và hướng dẫn demo tại docs/api/week-3.md,
  progress/week-3-review.md; đồng bộ khi preview khớp WBS và tên task.
- WBS 4.5–4.6 đạt đủ schema/API/acceptance/docs và được thêm vào tracking.
- 4.7 (tích hợp completion với grade/exam) và 4.8 (test/demo toàn tuần) tiếp tục theo
  trạng thái hiện có trên sheet; giao diện exam/grade thuộc task tiếp theo.
- Sync chỉ ghi F/G của 7 task mới (3.4–3.8, 4.5–4.6), không đổi tên/owner/deadline/
  layout hoặc công thức tổng tuần. Kiểm tra lại sau apply qua sync.py.
