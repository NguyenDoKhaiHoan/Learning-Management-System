# WBS 6.5 — Security tests AuthN/AuthZ, IDOR và file access

Checkpoint: 14/10/2026. Suite `backend/tests/integration/test_week6_access_security.py`
gọi HTTP trên MySQL thật và storage tạm; mỗi case có dữ liệu cách ly. Học viên thứ hai
được tạo/đăng nhập/ghi danh ACTIVE qua API để kiểm tra IDOR ngay trong cùng course.

| Nhóm | Kiểm chứng |
| --- | --- |
| AuthN | 15 trường hợp: thiếu credentials, sai scheme, malformed JWT, dùng refresh token làm access, sai signature, alg=none, expired, nbf tương lai, sai issuer/audience/type, sub dạng số/vượt BIGINT, thiếu exp, user không tồn tại; HTTP 401 + WWW-Authenticate + error/trace contract và security event |
| Claims giả mạo quyền | Token hợp lệ có thêm roles=ADMIN/permission vẫn không vượt quyền trong DB; /users trả 403 |
| AuthZ matrix | Anonymous/Student/Instructor ngoài course bị chặn tại 17 thao tác đọc/ghi account/role/audit/report/grade/question bank/review/exam/course/export; xác nhận không thêm audit nghiệp vụ/export, không đổi course/exam hoặc cấp ADMIN |
| Attempt IDOR | Student thứ hai ACTIVE không đọc, submit, autosave hay ghi telemetry vào attempt của bạn; đáp án/version/status giữ nguyên, không lộ is_correct/snapshot |
| Submission/file IDOR | Không xem metadata/nội dung file của học viên khác; đổi submission_id nhưng giữ file_id vẫn 404; submissions/mine chỉ trả bài của mình |
| Grade/notification IDOR | Draft và Published của bạn không xuất hiện trong grades/me; không gọi manager grade endpoint; đánh dấu notification của bạn không thay đổi is_read trong DB |
| File parent scope | Đổi course/module/lesson/resource ID không lấy được file; metadata không chứa location; tên ../../ được chuẩn hóa; MIME giả/HTML/empty/oversize bị chặn và không để file rác |
| Live file access | File hợp lệ tải đúng bytes; SUSPENDED/course Draft chặn ngay; ACTIVE cho phép lại; account LOCKED chặn token đã cấp; location tuyệt đối/đi ra ngoài storage bị 404 |
| Export ownership | Chỉ requester xem/tải job; Admin cũng không lấy job của người khác; list không lộ job; mất course.read hoặc bị thu hồi course_staff chặn download/status; lần tải bị chặn không ghi download audit |
| Private response | Lesson/submission/export CSV trả attachment với Cache-Control: no-store và X-Content-Type-Options: nosniff |

Security regression từ các tuần trước vẫn bắt buộc chạy cùng:

- `test_week2_mysql.py`, `test_week2_remaining.py`: refresh rotate/reuse/logout/expiry,
  current account/role/permission, self-enrollment impersonation, staff revoke trong lúc chờ lock.
- `test_week3_learning.py`, `test_week3_assignments.py`: private file validation, ownership,
  submission limits và audit rollback/cleanup.
- `test_week4_exams.py`, `test_week4_grading.py`: cross-course questions/answers/sources,
  grading key, stale version và grade visibility sau khi chờ lock.
- `test_week5_portals.py`: Admin account/dashboard scope và forum course boundary.
- `test_week6_security.py`, `test_week6_audit.py`, `test_week6_reports.py`: security persistence,
  telemetry/review scope, audit rollback, export live permission/worker/cancellation/CSV safety.
- `tests/unit/test_week1.py`: error/log sanitization và JWT claims; browser guard được kiểm
  trong Playwright và frontend unit suite.

Hai handler tải lesson/submission được bổ sung header chống cache và MIME sniffing sau
khi test mới phát hiện thiếu header. CSV export đã có chính sách này.

Từ `lms-platform/backend`, cấu hình `MYSQL_TEST_ADMIN_URL` bằng môi trường riêng:

```powershell
../../.venv/Scripts/python.exe -m pytest -q --strict-markers --require-mysql -m security
../../.venv/Scripts/python.exe -m pytest -q --strict-markers --require-mysql
```

`-m security` chạy 7 case chuyên biệt, trong đó matrix bao phủ 51 request bị từ chối.
Full suite bao gồm regression ở trên. Xem [checklist nghiệm thu](week-6-acceptance.md)
và [kết quả thực tế](../../progress/week-6-review.md). Phạm vi là bảo mật chức năng MVP;
pentest hạ tầng/dependency, malware scanning, rate limiting và hardening production
vẫn theo kế hoạch tuần 7–8.
