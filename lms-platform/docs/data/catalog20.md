# Bộ dữ liệu học tập 20 khóa học

Đã nạp vào database local `lms` ngày **20/10/2026**. Có 20 khóa học nội bộ,
40 chương, 80 bài học, 20 bài thực hành, 20 bài kiểm tra, 60 câu hỏi và 180 lựa chọn.
Mỗi câu có một đáp án đúng, giải thích và đường dẫn nguồn chính thức. Thông tin
người học, bài nộp, điểm số và sự kiện tương tác là **dữ liệu mô phỏng**, dùng
account `@example.test`; không phải hồ sơ người thật. Các khóa/đề do LMS biên soạn,
không phải khóa học hoặc kỳ thi chứng chỉ do Python, AWS, Google hay các bên tham
chiếu tổ chức.

## Nội dung và nguồn

20 chủ đề gồm Python, SQL/MySQL, Web, Git, Docker, HTTP API, pytest, authorization,
cấu trúc dữ liệu, tìm kiếm, pandas, ML, IAM, CI/CD, Scrum, accessibility, quản lý
công việc, tiếng Anh kỹ thuật, bảo vệ dữ liệu và trực quan hóa. Nội dung tiếng Việt
được biên soạn dựa trên tài liệu gốc; không sao chép nguyên bài của nhà xuất bản.

Từng khóa có mục tiêu, yêu cầu đầu vào, 4 bài học có nội dung, liên kết đọc thêm,
bài thực hành và rubric 40/30/30. Thời lượng 4 giờ là **ước lượng nội bộ**. Đề kiểm
tra nền tảng gồm 3 câu riêng theo môn, 10 điểm/câu, 15 phút, đạt từ 18/30, tối đa
3 lần làm. Cửa sổ làm bài mở từ 7 ngày trước đến 180 ngày sau lần nạp đầu tiên.
Seed không tự dời thời hạn của dữ liệu đã nạp khi chạy lại.

Danh sách 20 URL chính thức, HTTP status, tiêu đề trang, thời điểm kiểm tra và
checksum nằm trong [catalog20-sources.json](catalog20-sources.json). Đã kiểm tra
20/20 URL trả HTTP 200. Đây là bằng chứng truy cập nguồn; tính đúng của đáp án còn
được đối chiếu qua nội dung và các kiểm tra chấm điểm.

## Phạm vi bảng

**38/38 bảng nghiệp vụ có ít nhất 20 hàng**, giữ nguyên dữ liệu đã có ngoài mã
`CATALOG20_01`–`CATALOG20_20`. Chi tiết số hàng và kết quả kiểm tra trong
[catalog20-report.json](catalog20-report.json).

Năm bảng không được thêm hàng cho đủ số lượng vì có ý nghĩa hệ thống cụ thể:

| Bảng | Số hàng | Lý do |
|---|---:|---|
| `alembic_version` | 1 | Một migration head hiện hành |
| `cache_versions` | 1 | Singleton có `CHECK(id=1)` |
| `roles` | 3 | ADMIN, INSTRUCTOR, STUDENT được ứng dụng hỗ trợ |
| `permissions` | 3 | course.read, course.write, course.publish |
| `role_permissions` | 7 | Các grant thực sự của ba role trên |

Có 20 tệp bài nộp UTF-8 trong private storage, đã chạy scanner cấu hình local và
kiểm tra size/SHA-256; 20 CSV report có tệp thực tế. Development scanner là chế độ
kiểm tra local đã có trong dự án. Email của các account seed bị tắt; delivery
được ghi nhận `FAILED/SEED_EMAIL_DISABLED`, không giả lập gửi thành công.
Refresh token và security event được tạo bằng login/logout qua API thật; session
seed được revoke ngay sau khi đăng nhập. Attempt event được đánh dấu mô phỏng và
DISMISSED, không gắn cờ gian lận cho người thật.

## Sử dụng

Từ `lms-platform/backend`, sau khi bootstrap `demo_instructor`, ba role và migrate:

```powershell
# Mặc định chỉ đọc và kiểm tra; không thêm dữ liệu.
../../.venv/Scripts/python -X utf8 -m scripts.seed_catalog20 --allow-lms

# Nạp vào lms local; chạy lại giữ dữ liệu và lịch sử học đã tồn tại.
../../.venv/Scripts/python -X utf8 -m scripts.seed_catalog20 --apply --allow-lms
```

Script từ chối staging/production. Database demo/test có thể dùng tên
`lms_demo_*` hoặc `lms_test_*`. `--refine-initial` chỉ phục vụ thay bản nháp seed
ban đầu trong phiên làm việc này; không dùng để ghi đè lịch sử đã được sử dụng.

Đăng nhập bằng `demo_instructor` hiện có để quản lý đủ 20 khóa. Các account
`catalog_student_01` đến `catalog_student_20` học khóa tương ứng số thứ tự, với
password demo `Catalog20-Demo!2026`. Account mỗi khóa có một bài làm mẫu đã nộp và
còn hai lần thi. Password/role/status đã thay đổi sau seed được giữ nguyên.

## Kiểm chứng

- Ràng buộc FK của toàn schema không có hàng mồ côi.
- Mỗi đề có 3 câu, 3 lựa chọn/câu, đúng một đáp án; tổng điểm và điểm đạt hợp lệ.
- Snapshot bài làm có prompt/options đầy đủ, ID lựa chọn là số; kết quả câu,
  attempt, grade items, gradebook và history khớp nhau.
- Tiến độ mẫu 2/4 bài = 50%, bài thực hành và đề thi đã đạt; chưa hoàn tất khóa.
- Bài làm có timestamp đúng thứ tự, tệp thực tế khớp metadata và scanner.
- Integration test tạo schema MySQL riêng, seed từ đầu, login, xem snapshot đã
  nộp, làm thêm một attempt qua API và được chấm 30/30. Seed chạy lại giữ attempt
  mới và không tăng audit/file/khóa học.

```powershell
# MYSQL_TEST_ADMIN_URL được lấy từ environment, không đưa credential lên Git.
../../.venv/Scripts/python -m pytest -q tests/integration/test_catalog20.py `
  tests/unit/test_demo_seed.py --require-mysql
```

Hai test trên đạt; Ruff toàn backend/migration đạt. Bản sao database trước khi
hoàn thiện seed được lưu riêng tại `.local-logs/catalog20-before-refinement.sql`,
không đưa vào Git; tệp private cũng bị Git bỏ qua.
