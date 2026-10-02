# Tuần 4: WBS 4.1–4.6

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
Hết hạn được ghi nhận khi đọc attempt/eligibility hoặc thao tác attempt kế tiếp.
Từ WBS 4.5, lifespan API chạy worker quét deadline mỗi 5 giây, tối đa 100 attempt/lượt.
Worker không cần Student còn online hoặc enrollment còn Active. Khi API khởi động lại,
worker xử lý các attempt quá hạn còn lại; thời điểm nộp tự động luôn là `expires_at`.
Server luôn từ chối đáp án đến muộn.

Acceptance: `tests/integration/test_week4_exams.py` kiểm MySQL thật cho blueprint,
CRUD, validation/scope, timer, autosave/resume, snapshot, cạnh tranh request,
suspension và rollback khi audit lỗi. OpenAPI được xuất trong shared/contracts/openapi.json.

## WBS 4.5 — submit/auto-submit và auto-grading

Submit và worker dùng chung thao tác đóng bài/chấm điểm trong một transaction.
Khóa course → enrollment → exam → attempt → grade giữ nhất quán giữa autosave,
submit và nhiều worker. Các truy vấn đáp án/điểm dùng locking read để đọc commit mới
nhất sau khi chờ khóa, tránh snapshot cũ do authentication đã bắt đầu transaction.
Gọi submit lại không tăng version, không chấm lại, không tạo lịch sử/audit trùng.
Audit lỗi làm rollback cả trạng thái, đáp án đã chấm, điểm và lịch sử.

Chấm SINGLE/MULTIPLE/TRUE_FALSE bằng tập option đúng trong `question_snapshot`:
đúng toàn bộ tập được đủ điểm, sai/thừa/thiếu/bỏ trống được 0. Không có điểm từng phần.
Điểm dùng Decimal, tối đa 2 chữ số thập phân; input điểm có độ chính xác cao hơn bị 422.
`exam_answers` lưu `is_correct`/`points_awarded`; attempt lưu score và graded_at nội bộ.
Student không nhận answer key hoặc score từ API attempt.

Auto-grading tạo grade DRAFT và grade item theo từng câu. Với nhiều lần thi, lấy điểm
cao nhất khi grade vẫn là nháp tự động; điểm bằng nhau giữ lần trước. Instructor đã sửa
nháp hoặc công bố thì các lần thi tiếp theo vẫn được chấm nhưng không ghi đè grade đó.
Instructor điều chỉnh qua API grade. Không tự công bố điểm khi submit.

Có thể chạy worker riêng tại backend: `python -m src.jobs.processors.exam_expiry`.
API tự chạy worker nên local/demo/Docker không cần thêm service để tự nộp bài.
Legacy attempt không có question_snapshot không được tự suy ra đáp án hoặc điểm;
cần xử lý riêng trước khi sử dụng grading cho dữ liệu trước migration 0006.

## WBS 4.6 — grade items, draft/publish/revise, feedback/history

| Chức năng | API |
|---|---|
| Tạo grade thủ công | POST `/courses/{course_id}/grades` |
| List grade quản lý | GET `/courses/{course_id}/grades` |
| Chi tiết grade quản lý | GET `/grades/{grade_id}` |
| Sửa nháp | PUT `/grades/{grade_id}` |
| Công bố | POST `/grades/{grade_id}/publish` |
| Sửa điểm đã công bố | POST `/grades/{grade_id}/revise` |
| Lịch sử quản lý | GET `/grades/{grade_id}/history` |
| Điểm đã công bố của mình | GET `/courses/{course_id}/grades/me` |

Tạo thủ công cần `assessment_type` (ASSIGNMENT/EXAM), `assessment_id`, `enrollment_id`,
`source_id` (submission/attempt đã nộp đúng học viên và assessment), `feedback`, `items`.
Auto-grade EXAM đã tồn tại thì sửa nháp bằng PUT, không tạo thêm bản ghi.
Mỗi item có `item_key`, `label`, `score`, `max_score`, `feedback`; key duy nhất,
`0 <= score <= max_score`, tổng maximum phải bằng maximum của assessment/source.
Điểm grade được tính từ tổng items, client không gửi một score tổng độc lập.

Ví dụ sửa nháp:

```json
{
  "expected_version": 1,
  "feedback": "Đã kiểm tra bài làm",
  "items": [
    {"item_key": "overall", "label": "Kết quả", "score": 8, "max_score": 10,
     "feedback": "Cần trình bày rõ hơn"}
  ]
}
```

Publish nhận `{"expected_version":2}`. Revise dùng payload sửa nháp và thêm `reason`
không rỗng. Mỗi thay đổi tăng version; version cũ trả 409. Retry publish cùng version
trước/sau lần publish gần nhất trả lại grade và không thêm lịch sử.
Không sửa trực tiếp Published: revise đưa về DRAFT, ẩn điểm với Student đến khi công bố lại.
Mỗi revision lưu snapshot đầy đủ grade/items/feedback, actor, reason và timestamp;
history chỉ có thao tác INSERT, không có endpoint sửa/xóa lịch sử.

Quản lý cần Admin/Instructor + course.write + owner/course_staff; publish cần
course.publish. Student chỉ đọc grade Published của enrollment của mình, course
Published và enrollment Active/Completed; enrollment Suspended không đọc được.
`show_results` của exam chưa mở answer-key review: công bố grade là điều kiện hiển thị
điểm/feedback, đáp án đúng không được trả cho Student.

Migration `0007_grading` bổ sung grade_items, grade_history, feedback/source/version và
graded_at; snapshot lms.sql và OpenAPI đã cập nhật. Tích hợp điểm với completion (4.7)
và giao diện thi/điểm thuộc các task tiếp theo.

Demo API tự kiểm chứng trên MySQL tạm (cần MYSQL_TEST_ADMIN_URL):

```powershell
python -m pytest tests/integration/test_week4_grading.py -v
```

Kịch bản `test_grade_draft_publish_revise_history_and_visibility` chạy
exam → autosave → submit/chấm → sửa nháp → công bố → Student xem điểm → sửa/công bố lại.
