# Learning Management System (LMS)

## 1. Mục đích hệ thống

Learning Management System là nền tảng quản lý hoạt động dạy và học trực tuyến. Hệ thống hỗ trợ quản trị người dùng, tổ chức khóa học, phân phối nội dung, giao và nộp bài, kiểm tra trực tuyến, chấm điểm, trao đổi và báo cáo tiến độ học tập.

## 2. Vai trò người dùng

- **Quản trị viên (Admin):** quản lý tài khoản, vai trò, quyền truy cập, cấu hình hệ thống, nhật ký bảo mật và báo cáo toàn hệ thống.
- **Giảng viên (Instructor):** tạo và quản lý khóa học, nội dung học tập, bài tập, ngân hàng câu hỏi, kỳ thi, điểm số và trao đổi với người học.
- **Học viên (Student):** đăng ký khóa học, học nội dung, làm bài, nộp bài, tham gia kỳ thi, xem điểm và theo dõi tiến độ.

## 3. Quy trình nghiệp vụ chính

### 3.1. Quản lý người dùng và phân quyền

1. Quản trị viên tạo hoặc kích hoạt tài khoản.
2. Hệ thống gán vai trò và quyền tương ứng.
3. Người dùng đăng nhập và chỉ được truy cập các chức năng được cấp quyền.
4. Các hoạt động quan trọng được ghi nhận trong nhật ký kiểm toán và bảo mật.

### 3.2. Quản lý khóa học

1. Giảng viên tạo khóa học và khai báo thông tin cơ bản.
2. Giảng viên xây dựng cấu trúc bài học và tải nội dung lên hệ thống.
3. Khóa học được lưu nháp, xét duyệt hoặc công bố theo quy trình quản lý.
4. Học viên xem danh sách khóa học và đăng ký tham gia.

### 3.3. Học tập và theo dõi tiến độ

1. Học viên truy cập nội dung đã được cấp quyền.
2. Hệ thống ghi nhận trạng thái hoàn thành bài học, thời gian học và kết quả.
3. Học viên theo dõi tiến độ cá nhân.
4. Giảng viên và quản trị viên xem báo cáo tiến độ theo khóa học hoặc người học.

### 3.4. Bài tập và nộp bài

1. Giảng viên tạo bài tập, thời hạn và tiêu chí chấm.
2. Học viên nộp bài trước thời hạn bằng tệp hoặc nội dung trực tuyến.
3. Hệ thống lưu phiên bản và thời điểm nộp bài.
4. Giảng viên chấm điểm, nhận xét và trả kết quả.
5. Học viên xem điểm, nhận xét và trạng thái bài nộp.

### 3.5. Ngân hàng câu hỏi và kỳ thi

1. Giảng viên tạo, phân loại và quản lý câu hỏi.
2. Giảng viên cấu hình đề thi, thời lượng, số lần làm và cách tính điểm.
3. Học viên làm bài trong thời gian được phép.
4. Hệ thống tự động lưu bài, chấm các câu hỏi phù hợp và ghi nhận kết quả.
5. Các hoạt động bất thường được chuyển cho chức năng giám sát chống gian lận.

### 3.6. Diễn đàn, nhắn tin và thông báo

- Người dùng trao đổi trong phạm vi khóa học hoặc cuộc hội thoại được cấp quyền.
- Hệ thống gửi thông báo về khóa học, bài tập, kỳ thi, điểm số và sự kiện liên quan.
- Nội dung trao đổi và thông báo phải được phân quyền theo người nhận hoặc nhóm học tập.

### 3.7. Báo cáo và xuất dữ liệu

- Báo cáo người dùng, khóa học, đăng ký, tiến độ, điểm số và kết quả thi.
- Cho phép xuất dữ liệu theo quyền của người dùng.
- Dữ liệu xuất phải được ghi nhận và bảo vệ trong khu vực lưu trữ riêng.

## 4. Quy tắc nghiệp vụ cốt lõi

- Người dùng phải đăng nhập và có quyền phù hợp trước khi truy cập tài nguyên.
- Học viên chỉ được xem nội dung của khóa học đã được đăng ký hoặc cấp quyền.
- Bài nộp sau thời hạn phải tuân theo chính sách trễ hạn của bài tập.
- Điểm số chỉ được thay đổi bởi người có quyền chấm hoặc điều chỉnh điểm.
- Kỳ thi phải kiểm tra điều kiện tham gia trước khi bắt đầu.
- Tệp tải lên phải được kiểm tra quyền truy cập, loại tệp và khu vực lưu trữ.
- Hoạt động nhạy cảm phải có nhật ký kiểm toán.
- Dữ liệu cá nhân, bài nộp, đề thi và kết quả phải được bảo vệ khỏi truy cập trái phép.

## 5. Phạm vi chức năng

### Backend

Các module nghiệp vụ nằm trong `backend/src/modules`:

- Identity Access và User Role
- Course và Enrollment
- Learning Content và Learning Progress Analytics
- Assignment và Gradebook
- Question Bank và Quiz Exam
- Anti-Cheating
- Forum Messaging và Notification
- File Management
- Audit Security
- Integration và Reporting Export

### Frontend

Giao diện được tổ chức theo tính năng trong `frontend/src/features` và theo cổng người dùng trong `frontend/src/portals`:

- Admin portal
- Instructor portal
- Student portal

### Dữ liệu và hạ tầng

- `database`: migration, schema và dữ liệu khởi tạo.
- `storage`: bài tập, nội dung khóa học, tài nguyên kỳ thi, bài nộp và dữ liệu xuất.
- `infrastructure`: container, triển khai, giám sát và script vận hành.
- `shared`: constants, contracts, types và validation dùng chung.
- `docs`: API, kiến trúc, quy tắc nghiệp vụ và workflow.

## 6. Cấu trúc dự án

```text
lms-platform/
├── backend/          # API và xử lý nghiệp vụ phía máy chủ
├── database/         # Schema, migration và seed dữ liệu
├── docs/             # Tài liệu nghiệp vụ, API, kiến trúc và workflow
├── frontend/         # Giao diện theo tính năng và vai trò người dùng
├── infrastructure/   # Hạ tầng triển khai và giám sát
├── shared/           # Hợp đồng và kiểu dữ liệu dùng chung
├── storage/          # Khu vực lưu trữ tệp nghiệp vụ
└── tests/             # Acceptance, performance và security tests
```

## 7. Trạng thái hiện tại

Đã triển khai Tuần 1 — Phần 1 & Phần 2: cấu hình FastAPI, SQLAlchemy async/MySQL, 15 bảng P0 và migration Alembic đầu tiên. Xem [hướng dẫn backend](lms-platform/backend/README.md) để biết cấu trúc, quyết định thiết kế và lệnh chạy. Tên module Python sử dụng dấu gạch dưới `_` để import hợp lệ. Auth/RBAC, error contract và healthcheck thuộc phần tiếp theo.
