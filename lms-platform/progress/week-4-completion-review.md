# Checkpoint 05/10/2026 — hoàn thành tuần 4

## 4.7 Tích hợp điểm assignment/exam và completion

- Migration 0008_assessment_completion bổ sung hai gate tùy chọn:
  require_published_assignment_grades / require_published_exam_grades và
  minimum_grade_percent (0–100, mặc định 50). Quy tắc cũ giữ hành vi mặc định.
- Chỉ grade PUBLISHED và score/max_score đạt ngưỡng mới được tính; grade nháp,
  bài chưa thi/chưa chấm hoặc điểm dưới ngưỡng không làm course hoàn thành.
  Assignment yêu cầu cả submission và grade được tính một lần trong phần trăm.
- course_progress thêm passed_assignments, total_exams, passed_exams. Completion
  vẫn độc lập với Enrollment.status; không đóng quyền học sau khi hoàn thành.
- Publish/revise điểm refresh completion trong cùng transaction với grade/history/audit.
  Revise về Draft xóa completed_at; publish điểm đạt khôi phục completion.
- SQL locking reads đọc dữ liệu hiện tại sau khóa course/enrollment; Decimal kiểm
  ngưỡng chính xác. Không dùng phần trăm đã làm tròn để quyết định đạt.

## 4.8 Test và demo exam → chấm → công bố → xem điểm

- test_week4_completion.py chạy cùng API và MySQL thật: hai loại assessment,
  submission, autosave, submit, Draft ẩn với Student, publish, completion,
  revise, điểm 79.99 dưới ngưỡng 80, validation, scope và rollback khi audit lỗi.
- Suite liên quan tuần 3/4: **21 passed**. Toàn backend: **90 passed**, không skip,
  gồm schema upgrade/downgrade/import canonical. Frontend **11 unit passed**,
  build đạt; Ruff và contract drift đạt.
- `python -m scripts.demo_week4` tạo checkpoint trên **lms**, giữ dữ liệu hiện có,
  sử dụng API nghiệp vụ. Course DEMO_WEEK4 (id 2), exam id 1, grade id 1:
  Student không thấy Draft; sau publish xem điểm 10/10 và course hoàn thành.
  Chạy lại chỉ xác minh checkpoint, không tạo trùng dữ liệu.
- MySQL80 local đã Running. `lms` được upgrade từ 0006 qua 0007 lên **0008**.
  Database test lms_test_* là tạm thời và tự dọn, không thay database ứng dụng.

## Demo

Từ backend, chạy `../../.venv/Scripts/python.exe -m alembic upgrade head`, rồi
`../../.venv/Scripts/python.exe -X utf8 -m scripts.demo_week4`.
Tài khoản demo_instructor/demo_student dùng mật khẩu demo trong seed_week2.py.
Trong Swagger, Instructor xem GET /courses/2/grades và /grades/1/history;
Student xem GET /courses/2/grades/me và /courses/2/progress/me.
UI exam/grade riêng thuộc WBS 5.5; checkpoint tuần 4 được nghiệm thu qua API.
