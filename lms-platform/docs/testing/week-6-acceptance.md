# WBS 6.4 — Checklist nghiệm thu MVP

Checkpoint: 14/10/2026. Kiểm thử API chạy trên MySQL thật, database `lms_test_<uuid>`
và private storage tạm do fixture tạo/dọn. Không migrate, xóa hay seed database `lms`.
Browser dùng database riêng `lms_demo_e2e` theo cấu hình Playwright.

## Luồng nghiệm thu xuyên module

`backend/tests/integration/test_week6_acceptance.py` kiểm chứng một luồng liên tục:

1. Instructor tạo nội dung/đề thi, cấu hình completion rule và công bố course.
2. Student yêu cầu ghi danh PENDING; yêu cầu trùng trả 409; PENDING chưa đọc bài học.
   Instructor kích hoạt ACTIVE rồi Student học và hoàn thành lesson.
3. Student nộp hai phiên bản bài tập; lịch sử giữ nguyên, phiên bản thứ ba bị chặn.
   Hoàn thành lesson vẫn chưa hoàn thành course khi assessment bắt buộc chưa đạt.
4. Instructor tạo điểm assignment Draft. Student làm exam, autosave/resume giữ nguyên
   expires_at, submit lại không tạo điểm/lượt nộp trùng. Draft chưa hiển thị cho Student.
5. Công bố cả hai điểm đạt ngưỡng làm course_progress hoàn thành, giữ Enrollment ACTIVE.
   Student đọc feedback, thảo luận với Instructor và nhận/đánh dấu thông báo điểm.
6. Report manager phản ánh học viên hoàn thành; worker tạo CSV chứa đúng hai điểm
   Published. Admin truy vấn đủ audit ghi danh/nộp bài/công bố điểm/export/download.

Ba case deadline riêng xác nhận: cấm nộp trễ, chấp nhận trong cửa sổ trễ và từ chối
sau cửa sổ trễ. Bài nộp đúng hạn, version và audit trước đó được giữ nguyên.

Browser acceptance trong `frontend/tests/e2e/week6.spec.ts` thao tác UI thật để nộp
text/PDF thành hai version, chọn đáp án và chờ autosave, rời trang rồi resume giữ
đáp án/timer, nộp exam và xác nhận Draft còn ẩn. Sau bước manager tạo/công bố điểm
qua API, UI Student hiển thị đúng hai kết quả và feedback. Test tìm kiếm tuần 2 chờ
catalog hiển thị trước khi lấy số card, tránh đọc số 0 khi request còn đang chạy.

## Đối chiếu business rules và tiêu chí MVP

Đường dẫn bên dưới tính từ `backend/tests/integration`; mỗi dòng là điều kiện phải
đạt trong full regression, không chỉ sự hiện diện của file test.

| Checklist / rule | Kết quả phải quan sát | Bằng chứng tự động |
| --- | --- | --- |
| BR-ENR-01 | Không trùng student/course; chỉ ACTIVE được học/nộp/thi | `test_week6_acceptance.py`, `test_week2_remaining.py` (gồm concurrent enrollment), `test_week4_exams.py` |
| Publish content | Module có lesson/content; Draft/Archived không cho Student học; nội dung Published không sửa tùy ý | `test_week2_mysql.py` |
| BR-ASSIGN-01 | submitted_at, submitted_by, version, on-time/late; giới hạn attempts; file MIME/size | `test_week6_acceptance.py`, `test_week3_assignments.py` |
| BR-ASSIGN-02 | Draft ẩn; Published hiện; revise bắt buộc reason, version/history, feedback đúng | `test_week4_grading.py`, `test_week4_completion.py`, `test_week6_acceptance.py` |
| BR-EXAM-01 | Login, ACTIVE enrollment, Published exam, đúng cửa sổ và còn attempt | `test_week4_exams.py` |
| BR-EXAM-02 | Server timer không reset; deadline worker tự submit/chấm; race submit/worker idempotent | `test_week4_exams.py`, `test_week4_grading.py` |
| BR-EXAM-03 | Autosave/resume lưu đáp án; stale version bị 409; resume theo policy | `test_week4_exams.py`, `test_week6_acceptance.py` |
| Question/answer snapshot | Blueprint/randomization hợp lệ; chấm exact-set/decimal theo snapshot | `test_week4_exams.py`, `test_week4_grading.py` |
| BR-PROGRESS-01 | Completion theo rule và ngưỡng chính xác; revise có thể bỏ completion; enrollment không tự đổi | `test_week3_learning.py`, `test_week4_completion.py`, `test_week6_acceptance.py` |
| BR-AUDIT-01 | Publish/permission/grade/submission/review có actor/resource/trace/time; audit lỗi rollback | `test_week6_audit.py`, `test_week6_security.py`, `test_week4_grading.py` |
| BR-SEC-01 | Backend kiểm quyền file; không trả đường dẫn private hoặc đáp án cho Student | `test_week3_learning.py`, `test_week3_assignments.py`, `test_week4_exams.py` |
| Report/export | Filter/totals/page; Published mặc định; private CSV, retry/concurrency/cancellation/cleanup | `test_week6_reports.py`, `test_week6_acceptance.py`, `../unit/test_csv_export.py` |
| API failures | 401/403/404/409/413/422, error contract/trace, không lộ input/SQL/credentials | `test_week2_mysql.py`, `test_week3_assignments.py`, `../unit/test_week1.py` |
| Ba portal | Login/route guard; learning/assignment/exam/grades; notifications/forum; audit/security/report/export; mobile accessibility | `frontend/tests/e2e/week2.spec.ts`, `week5.spec.ts`, `week6.spec.ts` |
| Schema/demo | Canonical schema và migration round-trip; seed idempotent không mất tiến độ | `test_mysql.py`, `test_week2_remaining.py`, `../unit/test_demo_seed.py` |

## Chạy lại

Từ `lms-platform/backend`, cung cấp `MYSQL_TEST_ADMIN_URL` qua môi trường riêng
(tài khoản test có CREATE/DROP DATABASE); không ghi credentials vào repository:

```powershell
../../.venv/Scripts/python.exe -m pytest -q --strict-markers --require-mysql -m acceptance
../../.venv/Scripts/python.exe -m pytest -q --strict-markers --require-mysql
../../.venv/Scripts/ruff.exe check src tests scripts ../database/migrations
../../.venv/Scripts/python.exe scripts/export_contracts.py --check
../../.venv/Scripts/python.exe -m unittest discover -s ../progress/tests -v
```

`--require-mysql` trả lỗi trước collection nếu thiếu URL, tránh full suite báo thành
công khi integration bị skip. CI dùng cùng cờ và MySQL service riêng.

Từ `lms-platform/frontend`, dùng cấu hình development/test kết nối MySQL cho demo E2E:

```powershell
npm test
npm run build
npm run test:e2e
```

Kết quả chạy thực tế được ghi trong [review tuần 6](../../progress/week-6-review.md).
Đây là nghiệm thu tự động MVP; UAT và release candidate thuộc WBS 6.6–6.8.
