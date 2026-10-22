# User journeys MVP

## Instructor xây và công bố khóa học

Instructor đăng nhập → tạo course Draft → tạo module/lesson/resource → cấu hình
assignment hoặc exam → đặt completion rule → publish. Mỗi thay đổi được kiểm tra
course scope; publish và thay đổi điểm ghi audit. Course chưa publish không xuất hiện
trong luồng học viên.

## Student học và hoàn thành

Student đăng nhập → gửi enrollment request → staff chuyển ACTIVE → mở lesson và ghi
progress → nộp assignment hoặc mở exam trong cửa sổ server → autosave/resume → submit.
Worker xử lý deadline/grade; chỉ grade Published được hiển thị. Completion chỉ đạt khi
tất cả lesson và assessment bắt buộc thỏa rule; trạng thái enrollment vẫn ACTIVE.

## Manager kiểm tra và bàn giao

Admin/instructor mở report theo scope → lọc learner/gradebook → tạo export job → worker
ghi CSV private → requester tải file sau khi kiểm tra lại quyền. Admin xem audit/security
để đối chiếu trace; vận hành chạy migration/seed rehearsal, health check và backup
restore trước khi phát hành.

## Trạng thái lỗi bắt buộc

Mọi màn hình có loading, empty, error, forbidden và success. HTTP 401 kích hoạt refresh
rotation một lần; 403 giữ phiên và hiển thị từ chối; 404 không tiết lộ resource khác
scope. Frontend không lưu token vào localStorage/sessionStorage và gắn nội dung API qua
text content an toàn.
