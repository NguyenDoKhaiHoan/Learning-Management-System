# Phạm vi MVP và checkpoint tuần 1

Ngày: 09/09/2026. Cơ sở: `ke_hoach_build_lms.docx` mục 5–8 và yêu cầu thực hiện
các hạng mục còn lại tuần 1 trong phiên làm việc này. Đây là baseline triển khai;
không phải biên bản UAT hay tuyên bố đã có đầy đủ nghiệp vụ của tuần 2–6.

## Quyết định kiến trúc

- FastAPI, Python 3.11+, MySQL 8.0.16+ / InnoDB / utf8mb4_unicode_ci.
- SQL viết trực tiếp, bind parameters qua SQLAlchemy Core + aiomysql; không ORM/SQLModel.
- Alembic migration thủ công; giữ revision 0001_p0 đã áp dụng.
- Modular Monolith, presentation → application → domain; infrastructure triển khai SQL.
- Access token HS256 có iss/aud/exp/iat/nbf/sub/jti/token_type; role và account status
  lấy từ DB mỗi request. Quyền theo tài nguyên bổ sung trong use case tương ứng.
- API v1: success `{code,message,data,trace_id}`, error `{code,message,details,trace_id}`.
- Local Docker ở cổng 8001; release production/hardening là mục tiêu tuần 7–8.

## Backlog đã ưu tiên

| Ưu tiên | Phạm vi | Mốc | Điều kiện hoàn thành |
|---|---|---|---|
| P0 | Nền tảng, DDL, connection, health, contracts, trace, JWT/RBAC skeleton, CI | Tuần 1 | Test HTTP/SQL đạt; me bảo vệ bằng JWT; quy trình build/test có tài liệu |
| P0 | Login, password hashing, refresh/logout, account status, role management | Tuần 2 | Đăng nhập đúng role; inactive/locked bị chặn; revoke/rotation có test |
| P0 | Course/module/lesson metadata, publish, enrollment, staff | Tuần 2 | Admin/Instructor công bố; Student ghi danh; không trùng và kiểm scope |
| P0 | Private files, lesson access/progress, completion, assignment/submission version | Tuần 3 | Student học/nộp bài; kiểm deadline, file, permission, history |
| P0 | Gradebook và exam core | Tuần 4 | Timer server, autosave, auto-submit, grade release và audit |
| P1 | Question bank/blueprint, randomization bản cơ bản | Tuần 4 | Đủ phục vụ exam MVP; không làm adaptive test |
| P0 | Ba portal và luồng frontend MVP | Tuần 5 | Loading/empty/error/forbidden/success; backend kiểm quyền |
| P1 | Notification in-app và forum cơ bản | Tuần 5 | Membership/scope; thông báo theo event |
| P0 | Audit, acceptance/security tests, demo seed và release candidate | Tuần 6 | Luồng login → enrollment → learning → assessment → grade → completion |
| P1 | Anti-cheating event, report/grade export cơ bản | Tuần 6 | Event không tự kết luận gian lận; export theo quyền |
| P1 | Performance, queues, cache theo scope, scanning, backup/restore | Tuần 7 | Có benchmark và bằng chứng restore |
| P0 | UAT, deployment rehearsal, docs và bàn giao | Tuần 8 | Checklist release, hướng dẫn vận hành và backlog phase 2 |
| P2 | SSO/SIS, payment, video proctoring, adaptive test, BI nâng cao, PWA | Sau MVP | Chỉ nhận vào sprint khi có yêu cầu scope mới |

## Checklist tuần 1

- Khung dự án/config/SQL schema 14 bảng/migration/health/Docker hoạt động.
- Response model + handler 401/403/404/409/422/500; validation không lộ input.
- Trace ID trong header và body; JSON log có status/duration/route template.
- JWT signature/claims và role DB được kiểm tra; user inactive/locked/deleted bị chặn.
- GET `/api/v1/auth/me`; helper `require_roles(["ADMIN", "INSTRUCTOR"])` tái sử dụng.
- Shared JSON Schema/OpenAPI/TypeScript types; CI lint/test/MySQL/migration/contract drift;
  PR template có checklist permission, SQL, transaction, audit và tests.

CI workflow có trong repository và các bước được chạy local. Chỉ có thể xác nhận
GitHub Actions run từ xa sau khi commit/push lên GitHub; không đánh đồng việc tạo
workflow với bằng chứng một remote run đã pass.

## Không kéo sang tuần 1

Không triển khai public login/refresh/reset-password, CRUD course/enrollment, UI portal,
audit nghiệp vụ hoàn chỉnh hoặc production deployment trong checkpoint này. Auth
skeleton không chứng minh toàn bộ module Identity hoàn thành. Không seed tài khoản
mặc định/mật khẩu demo vào database thật để thử JWT.
