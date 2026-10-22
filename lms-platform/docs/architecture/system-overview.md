# Kiến trúc hệ thống LMS — checkpoint tuần 8

## Phạm vi runtime

LMS là modular monolith gồm FastAPI backend, MySQL 8.0 và Vite/TypeScript
frontend. Backend là nơi quyết định quyền; frontend chỉ điều hướng và hiển thị trạng
thái. `backend/src/main.py` tạo app, đăng ký router, middleware trace/metrics và các
worker nền. Migration SQL được quản lý độc quyền bằng Alembic trong
`database/migrations`.

```text
Browser
  └─ Vite/static web ── /api/v1 ── FastAPI
                                  ├─ identity / roles / audit-security
                                  ├─ course / enrollment / content / files
                                  ├─ learning / assignment / exam / gradebook
                                  ├─ forum / notification / reports / exports
                                  └─ health + metrics
                                      └─ MySQL (transaction boundary per request)
```

## Ranh giới module

Mỗi module giữ presentation router, application use case, domain rules và
infrastructure repository/adapter. Repository chỉ thực hiện SQL tham số hóa; use
case sở hữu commit/rollback. Các aggregate cần lịch sử (submission, attempt, grade,
audit, progress) không bị ghi đè. File riêng nằm ngoài web root, được kiểm tra scope
và scan trước khi phát hành.

Các worker expiry exam, export CSV và email notification chạy trong lifespan của
app. Job bền vững trong MySQL có idempotency key, retry hữu hạn và lock cạnh tranh.
Dashboard cache chỉ là tối ưu hóa; authorization sống luôn được kiểm tra trước khi
trả dữ liệu.

## Luồng triển khai

1. Tạo database rỗng và chạy `alembic upgrade head`.
2. Chạy seed idempotent trong `backend/scripts/seed_week2.py`; seed không ghi đè
   account, password hoặc tiến độ đã tồn tại.
3. Khởi động API với `APP_ENV` phù hợp; kiểm tra `/livez`, `/healthz` và `/metrics`.
4. Phục vụ frontend build tĩnh và proxy `/api` tới backend.

Migration hiện hành được xác nhận bởi `alembic current`; không chạy snapshot SQL lên
database đã có dữ liệu. Secret JWT, database và SMTP chỉ lấy từ môi trường/secret
manager, không đưa vào Git.
