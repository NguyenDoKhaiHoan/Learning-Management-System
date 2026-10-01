# Tuần 4: WBS 4.1–4.4

Ứng dụng và demo dùng database **lms** xuyên suốt. Chạy tại `backend`:

```powershell
../../.venv/Scripts/python -m alembic upgrade head
../../.venv/Scripts/python -m scripts.run_demo
```

`database/schemas/shared/lms.sql` là file SQL UTF-8 duy nhất để khởi tạo database
`lms` trống. Database có dữ liệu dùng `alembic upgrade head`; không import lại snapshot.
Xuất lại snapshot sau mỗi thay đổi: `python -m scripts.export_schema`.
Migration lịch sử giữ nguyên để nâng cấp dữ liệu hiện có. Các database demo cũ được giữ
nguyên; script không xóa hay tự trộn dữ liệu có ID trùng nhau. Test migration dùng
`lms_test_<uuid>` tạm và tự dọn, tránh chạy DROP trên database ứng dụng.

Các API dưới đây có prefix `/api/v1`, JWT và success/error envelope có trace ID.
Quyền quản lý dùng role Admin/Instructor, permission course.write và owner/course_staff;
publish cần course.publish. Student cần course.read, role Student, course Published và
enrollment Active ở mỗi thao tác. Thu hồi enrollment chặn cả resume, save và submit.

| Chức năng | API |
|---|---|
| Tạo/list bank | POST/GET `/courses/{course_id}/question-banks` |
| Tạo/list category | POST/GET `/question-banks/{bank_id}/categories` |
| Tạo/list question | POST/GET `/question-banks/{bank_id}/questions` |
| Tạo/list exam | POST/GET `/courses/{course_id}/exams` |
| Sửa exam Draft | PUT `/courses/{course_id}/exams/{exam_id}` |
| Chi tiết/xóa exam Draft | GET/DELETE `/exams/{exam_id}` |
| Publish | POST `/exams/{exam_id}/publish` |
| Eligibility | GET `/exams/{exam_id}/eligibility` |
| Bắt đầu attempt | POST `/exams/{exam_id}/attempts` |
| Resume/status | GET `/attempts/{attempt_id}` |
| Autosave | PUT `/attempts/{attempt_id}/answers/{question_id}` |
| Submit | POST `/attempts/{attempt_id}/submit` |

Question hỗ trợ SINGLE, MULTIPLE, TRUE_FALSE; difficulty EASY/MEDIUM/HARD và category
thuộc bank. List lọc bằng `difficulty`/`category_id`. Option có key/text/is_correct;
single/true-false phải có đúng một đáp án đúng. Chỉ API quản lý bank trả đáp án đúng.

Exam nhận `opens_at`, `due_at` có timezone, `duration_seconds`, `max_attempts`,
`allow_resume` và một trong hai cách chọn đề: `questions` (question_id/position/points)
hoặc `blueprint` (bank_id/category_id/difficulty/question_type/question_count/points_each).
Mỗi blueprint có tối đa một dòng cho mỗi loại câu hỏi. Publish chọn ngẫu nhiên đủ số
câu phù hợp, đóng băng danh sách exam; thiếu câu trả 409 và rollback. Exam Published
không sửa/xóa. Cho phép quản lý assessment trên course Published.

Attempt chỉ bắt đầu trong `[opens_at, due_at)`, một attempt đang làm trên mỗi
student/exam. Khóa course → enrollment → exam → attempt bảo vệ request đồng thời.
Thời gian lấy từ MySQL UTC, `expires_at=min(started_at+duration,due_at)`; resume không
gia hạn. Mỗi attempt lưu snapshot câu hỏi, lựa chọn và thứ tự riêng, không phụ thuộc
các thay đổi câu hỏi về sau. Response loại bỏ is_correct và score chưa công bố.

Autosave nhận ví dụ `{"selected_option_ids":[12],"expected_version":0}`. Response
trả `server_version` mới; lần save tiếp theo gửi version đó. Version cũ trả 409;
câu hỏi/option ngoài đề trả 422. Gửi mảng rỗng để xóa lựa chọn. Reload/resume trả đáp án
đã lưu, version, server_time và remaining_seconds. `allow_resume=false` chặn GET resume
trong lúc đang làm; vẫn cho phép save/submit từ phiên đang mở.

State: IN_PROGRESS → SUBMITTED hoặc AUTO_SUBMITTED. Submit lặp lại là idempotent.
Hết hạn được ghi nhận khi đọc attempt/eligibility hoặc thao tác attempt kế tiếp;
không có worker tự quét nền trong phạm vi 4.1–4.4. Server luôn từ chối đáp án đến muộn.
Auto-grading, công bố điểm và UI thi không được đánh dấu hoàn thành trong checkpoint này.

Acceptance: `tests/integration/test_week4_exams.py` kiểm MySQL thật cho blueprint,
CRUD, validation/scope, timer, autosave/resume, snapshot, cạnh tranh request,
suspension và rollback khi audit lỗi. OpenAPI được xuất trong shared/contracts/openapi.json.
