# WBS 7.3 — Cache theo scope và invalidation

Cache dữ liệu aggregate cho `GET /reports/overview` và
`GET /dashboard/instructor`. Khóa gồm loại dashboard, actor ID, các role hiện tại
và phiên bản dữ liệu bền trong MySQL. AuthN, role, account status và permission
vẫn truy vấn trực tiếp mỗi request; dữ liệu Instructor vẫn lấy theo course
ownership/course_staff. Phân trang áp dụng trên bản sao riêng của dữ liệu cache.

Migration **0014_dashboard_cache** tạo singleton `cache_versions`. Mọi audit log
nghiệp vụ tăng version trong cùng transaction với mutation. Commit làm các cache
ở mọi API process dùng key mới; rollback giữ version và dữ liệu cũ. Dùng version
counter được InnoDB khóa khi tăng, tránh lỗi thứ tự commit của `MAX(audit_id)`.
Cache đọc version và aggregate trong cùng snapshot REPEATABLE READ mới, sau khi
đóng snapshot chỉ đọc của dependency xác thực. Vì vậy kết quả cũ không thể bị
gắn vào version mới khi request phải chờ transaction khác.

Cache ở RAM từng app, TTL 15 giây, giới hạn 256 entry LRU, gộp cache miss đồng thời,
không lưu lỗi/cancel, deepcopy để request không làm thay đổi cache của request sau.
Có bộ đếm `hits/misses` nội bộ cho kiểm chứng; không mở endpoint debug công khai.
Student progress, grades, eligibility, file và export luôn lấy dữ liệu trực tiếp.

```dotenv
DASHBOARD_CACHE_TTL_SECONDS=15
DASHBOARD_CACHE_MAX_ENTRIES=256
```

Đặt TTL=0 để tắt cache. Invalidation hiện tại là toàn dashboard (đổi dữ liệu bất kỳ
đều tăng counter), ưu tiên tính đúng; khi lưu lượng ghi lớn, đo contention rồi
tách counter theo course. Script bảo trì ghi SQL ngoài application phải tăng
`cache_versions.version` trong cùng transaction hoặc chấp nhận trễ tối đa TTL.
Schema migration phải chạy trước khi khởi động phiên bản ứng dụng này.

Kiểm chứng MySQL: cache hit tránh gọi lại aggregate; không lẫn hai Instructor;
phân trang không phá cache; staff grant/revoke cập nhật ngay; permission/account
revocation vẫn chặn cache hit; hai app có cache RAM riêng cùng thấy commit;
rollback không thay đổi counter/kết quả. Unit test kiểm TTL/LRU/deepcopy,
gộp miss và bỏ lỗi/cancel. Regression Admin/dashboard/forum tuần 5 đạt.

[Lượt baseline sau thay đổi](week-7-cache-baseline.json) dùng cùng dataset/budget
đạt cả 6 operation: Admin overview 3 SQL/op (trước 4), p95 17,80 ms (trước 23,24).
Số đo latency phụ thuộc tải máy; SQL/op và các ca scope/invalidation là bằng chứng
trực tiếp về hành vi cache. Job export tăng 2 SQL/op do audit tăng cache version.

```powershell
../../.venv/Scripts/python -m pytest -q tests/unit/test_cache.py tests/integration/test_week7_cache.py tests/integration/test_week5_portals.py --require-mysql
```
