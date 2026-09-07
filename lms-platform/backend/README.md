# Tuần 1 — Phần 1 & Phần 2

## Chạy Docker với database `lms` đã có trên Windows

Dockerfile và `../compose.yml` đóng gói backend cùng Alembic. MySQL tiếp tục chạy
bằng dịch vụ Windows hiện có. Container dùng `host.docker.internal` thông qua
`DB_HOST_OVERRIDE`, còn khi chạy Python trên Windows dùng host trong DATABASE_URL.
Đây là cách kết nối host được [Docker Desktop hướng dẫn](https://docs.docker.com/desktop/features/networking/networking-how-tos/).

1. Điền tài khoản MySQL thực tế vào `backend/.env`, database là `lms`. Không dùng
   tài khoản/mật khẩu của Compose MySQL cũ trừ khi bạn đã tự tạo tài khoản đó.
   Nếu file đã có JWT_SECRET ngẫu nhiên thì giữ nguyên. Percent-encode ký tự đặc biệt
   trong username/password của URL. Không thêm dấu nháy quanh giá trị `.env`, vì
   Compose dùng `format: raw` để bảo toàn dấu `$` trong secret. Cần Compose 2.30+.
2. Bật Docker Desktop và dịch vụ MySQL80.
3. Từ thư mục `lms-platform`, chạy:

```powershell
docker compose build
# Chỉ kiểm tra kết nối database trước khi thực hiện migration:
docker compose run --rm --no-deps api python -m src.core.database.check
docker compose run --rm migrate
docker compose run --rm migrate python -m alembic check
docker compose up -d --wait api
docker compose ps
Invoke-RestMethod http://localhost:8001/healthz
```

Cổng mặc định là **8001**, vì cổng 8000 trên máy hiện tại đã được ứng dụng khác dùng.
Đặt `$env:LMS_API_PORT = '8002'` trước khi chạy Compose nếu cần đổi cổng.

Nếu build báo `CERTIFICATE_VERIFY_FAILED` như mạng trên máy hiện tại, thay bước
`docker compose build` bằng lệnh sau (chạy từ `lms-platform`):

```powershell
./infrastructure/scripts/build-backend.ps1 -UseWindowsCertificates
```

Script chuyển public root CA của Windows vào bước pip install qua BuildKit secret.
Chứng chỉ không được lưu vào image và xác thực TLS vẫn được bật.

Đã xác nhận trong phiên triển khai: tạo database `lms` theo yêu cầu, migration `0001_p0`
thành công, Alembic check không có drift; API Docker healthy, `/docs` trả 200 và
`/healthz` trả `{"status":"ok","database":"ok"}`. **12 test đạt**, gồm integration
upgrade/downgrade, Unicode, UNIQUE, FK và CHECK trên database thử nghiệm riêng.

Sau khi chạy, `/livez` trả 200 khi API sống; `/healthz` trả 200 khi SELECT 1 thành công
và 503 khi database không sẵn sàng. `/docs` có trong development. Migration được chạy
riêng một lần mỗi lần nâng cấp trước khi khởi động API; không tự chạy trong từng worker.
Nếu database `lms` đã có bảng, cần đối chiếu schema trước khi áp dụng revision đầu tiên.

```powershell
docker compose logs --tail 100 api
docker compose stop api
docker compose down
```

Image chạy bằng user không phải root, filesystem chỉ đọc, log được xoay vòng,
chỉ mở API trên localhost:8001. `.env` không được copy vào image. Runtime dependencies
được khóa riêng trong `requirements.runtime.lock.txt`, không cài pytest/ruff vào image.
Container vẫn cần MySQL cho phép tài khoản kết nối từ đường mạng Docker; nếu gặp
Access denied, cấu hình tài khoản ứng dụng và quyền trên `lms.*` tại MySQL. Không tự
đổi mật khẩu root hoặc bật quyền root từ mọi host. Nếu gặp Connection refused/timeout,
kiểm tra MySQL listener và Windows Firewall theo mạng Docker đang dùng.

File `infrastructure/containers/compose.mysql.yml` là lựa chọn tạo MySQL development
riêng từ trước; không cần khởi động file đó để dùng database Windows hiện tại.

Đã triển khai nền tảng FastAPI và schema P0 trực tiếp theo cấu trúc repository.
Phần 3 (response contract/exception handlers) và phần JWT/RBAC
là bước tiếp theo; bản này chưa cung cấp API đăng nhập hay API nghiệp vụ.

## 1. Cấu trúc và trách nhiệm

```text
lms-platform/
├── backend/
│   ├── pyproject.toml
│   ├── requirements.lock.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── src/
│   │   ├── main.py                  # create_app, lifespan, dispose engine
│   │   ├── config/config.py         # Settings, get_settings
│   │   ├── core/database/
│   │   │   ├── database.py          # AsyncEngine, session factory, dependency
│   │   │   └── models/
│   │   │       ├── base.py          # tracking, soft delete, naming convention
│   │   │       └── registry.py      # metadata đầy đủ cho Alembic
│   │   └── modules/
│   │       ├── identity_access/     # User, RefreshToken
│   │       ├── user_role/           # Role, Permission và bảng liên kết
│   │       ├── course/              # Course
│   │       ├── learning_content/    # CourseModule, Lesson, LessonResource
│   │       ├── enrollment/          # Enrollment, CourseStaff
│   │       ├── audit_security/      # AuditLog, SecurityEvent
│   │       └── ...                 # Các module đã có, chưa triển khai nghiệp vụ
│   └── tests/
│       ├── unit/                   # Settings, DDL, migration offline
│       └── integration/            # Migration và constraints trên MySQL thật
├── database/
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/0001_p0.py
│   └── schemas/shared/0001_p0.sql   # SQL được xuất từ migration
└── infrastructure/containers/compose.mysql.yml
```

Mỗi module giữ nguyên bốn tầng đã có:

```text
<module>/
├── application/       # use case, transaction boundary, repository interfaces khi cần
├── domain/enums.py    # trạng thái nghiệp vụ, không phụ thuộc SQLAlchemy/FastAPI
├── infrastructure/models.py  # ánh xạ lưu trữ SQLAlchemy 2
└── presentation/      # router, request/response schema (bước sau)
```

Tên thư mục backend có dấu `-` được đổi thành `_` để dùng Python import thông thường.
Frontend không cần áp dụng quy tắc tên Python. Không gom tất cả model vào `core`;
`registry.py` chỉ tập hợp metadata. Liên kết xuyên module dùng FK và ID, chưa thêm
lazy relationship để tránh truy vấn ngầm gây `MissingGreenlet` với async ORM.

### Cấu hình và kết nối

`Settings` đọc biến môi trường trước, sau đó `.env` ở backend. `DATABASE_URL` và
`JWT_SECRET` bắt buộc, dùng `SecretStr` để che trong repr; secret mẫu bị từ chối.
URL bắt buộc `mysql+aiomysql`, có database, host, username và charset utf8mb4.
Mật khẩu chứa `@`, `%`, `/` phải percent-encode trong URL.

Engine có pool giới hạn, `pool_pre_ping`, recycle connection, timeout kết nối,
che tham số SQL, session timezone UTC và strict SQL mode. Mỗi request có session
riêng; không dùng một session chung giữa nhiều coroutine. Lifespan giải phóng pool.
Engine không tự tạo bảng lúc khởi động; migration là nguồn quản lý schema.

Dependency không tự commit sau khi trả response. Use case ghi dữ liệu phải xác định
transaction trước truy vấn đầu tiên vì SELECT cũng có thể bắt đầu transaction:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.course.infrastructure.models import Course

async def create_course(session: AsyncSession, actor_id: int, code: str, title: str) -> int:
    async with session.begin():
        course = Course(code=code, title=title, created_by=actor_id)
        session.add(course)
        await session.flush()
        course_id = course.id
    return course_id
```

Khi auth dependency đã truy vấn bằng cùng session, use case phải tiếp quản transaction
đã bắt đầu và commit/rollback rõ ràng; không lồng `session.begin()` một cách máy móc.

## 2. Schema MySQL

Yêu cầu MySQL **8.0.16+** để CHECK thực sự được thực thi. Tất cả 15 bảng nghiệp vụ
dùng InnoDB, charset `utf8mb4`, collation `utf8mb4_unicode_ci`. Charset và collation
là hai thuộc tính khác nhau. Digest/token family dùng collation ASCII binary riêng
để so sánh chính xác. Bảng `alembic_version` do Alembic quản lý, không phải entity nghiệp vụ.

Mọi bảng có `id BIGINT UNSIGNED AUTO_INCREMENT`, `created_at DATETIME(6)` và
`updated_at DATETIME(6)`. MySQL tự gán timestamp và tự cập nhật `updated_at`, kể cả
khi ghi bằng SQL trực tiếp. Tất cả thời gian lưu UTC; MySQL DATETIME không giữ timezone.
Client SQL bên ngoài cũng cần `SET time_zone = '+00:00'`.

| Bảng | Dữ liệu và ràng buộc chính |
|---|---|
| users | email UNIQUE, username UNIQUE, hashed_password; ACTIVE/INACTIVE/LOCKED, mặc định INACTIVE; soft delete |
| roles | code UNIQUE, name, description; code chuẩn ADMIN/INSTRUCTOR/STUDENT |
| permissions | code UNIQUE, description; ví dụ course.read, course.write |
| user_roles | FK user_id, role_id; UNIQUE(user_id, role_id) |
| role_permissions | FK role_id, permission_id; UNIQUE(role_id, permission_id) |
| refresh_tokens | user_id, token_hash UNIQUE, family_id, expires_at, revoked_at; expires_at > created_at |
| courses | code UNIQUE, title, description, created_by; DRAFT/PUBLISHED/ARCHIVED; soft delete |
| modules | course_id, title, position > 0; UNIQUE(course_id, position); soft delete |
| lessons | module_id, title, position > 0, content, lesson_type, is_preview; UNIQUE(module_id, position); soft delete |
| lesson_resources | lesson_id, title, resource_type, location, mime_type, size_bytes; soft delete |
| enrollments | student_id, course_id, status, completed_at; UNIQUE(student_id, course_id) |
| course_staff | course_id, user_id, role; UNIQUE(course_id, user_id) |
| audit_logs | actor_id nullable, action, resource, resource_id, timestamp, ip_address, trace_id, details JSON |
| security_events | actor_id nullable, event_type, severity, ip_address, trace_id, details JSON |

Enum dùng Python `StrEnum` và MySQL native ENUM, kiểm tra chuỗi khi bind qua ORM:

- LessonType: VIDEO, ARTICLE, DOCUMENT, LIVE.
- ResourceType: FILE, LINK. FILE lưu private object key; LINK lưu URL cần kiểm tra tại application.
- EnrollmentStatus: PENDING, ACTIVE, SUSPENDED, COMPLETED; mặc định PENDING.
  COMPLETED bắt buộc completed_at; trạng thái khác yêu cầu completed_at NULL.
- CourseStaffRole: INSTRUCTOR, ASSISTANT; đây là vai trò phạm vi khóa học, khác role toàn hệ thống.
- SecuritySeverity: INFO, WARNING, CRITICAL.
- SecurityEventType: LOGIN_SUCCEEDED, LOGIN_FAILED, TOKEN_REVOKED,
  TOKEN_REUSE_DETECTED, ACCESS_DENIED, PASSWORD_CHANGED, ACCOUNT_LOCKED.

### Quyết định thiết kế cần biết

1. FK đều `ON DELETE RESTRICT`. Xóa cứng user/course không âm thầm xóa enrollment,
   token hay audit. Quy trình purge cần thiết kế riêng theo chính sách lưu trữ.
2. Soft delete chỉ áp dụng user, course và nội dung. Truy vấn ở bước sau phải chủ động
   lọc `deleted_at IS NULL`, kể cả các ancestor của lesson. Chưa có global ORM filter.
3. UNIQUE email/username/code và position vẫn giữ chỗ sau soft delete. Khôi phục hoặc
   cập nhật bản ghi cũ thay vì tạo bản trùng. Enrollment tái kích hoạt trên bản ghi cũ.
   Sắp xếp lại position cần vị trí tạm vì MySQL kiểm tra UNIQUE ngay khi UPDATE.
4. Index FK được khai báo riêng hoặc được bao phủ bởi cột đầu của composite UNIQUE/index.
   Có index status, email/username, course+status, actor+time, trace_id và token expiration.
   Không lập thêm index đơn trùng với tiền tố index đã có.
5. Collation mặc định so sánh email/username không phân biệt hoa thường và dấu.
   Chuẩn hóa email/username tại application trước khi ghi; đổi collation nếu sản phẩm
   cần phân biệt dấu. Không tái sử dụng email sau soft delete trong thiết kế này.
6. FK đảm bảo user tồn tại; application phải kiểm tra user ACTIVE, role STUDENT,
   course PUBLISHED, quyền giảng viên và chuyển trạng thái hợp lệ. Schema không tự
   thực thi các chính sách xuyên aggregate này.
7. Refresh token chỉ lưu SHA-256 digest của token ngẫu nhiên đủ mạnh. `family_id`
   hỗ trợ revoke cả chuỗi khi phát hiện reuse; rotation và locking sẽ viết ở phần Auth.
   Không lưu JWT nguyên bản hoặc mật khẩu rõ. Roles/permissions chưa được seed.
8. Audit/security không soft delete; chính sách append-only cần DB grants của tài khoản
   runtime để cấm UPDATE/DELETE. `updated_at` vẫn tồn tại theo quy ước tracking.
   Không ghi password, token hay secrets vào details JSON. actor_id NULL dành cho
   tác vụ hệ thống hoặc người chưa xác thực, không phải user ID giả.

### Migration

`env.py` nạp registry trước khi autogenerate và chạy Alembic sync qua
`AsyncConnection.run_sync`. Online lấy URL trực tiếp từ Settings, không nội suy password
vào alembic.ini. Offline chỉ cần dialect MySQL nên không yêu cầu secret/database.

`0001_p0.py` là snapshot độc lập, có upgrade theo thứ tự FK và downgrade ngược lại.
Không import model hiện tại trong revision. Revision ban đầu được render từ metadata
bằng Alembic operations rồi kiểm tra offline; hiện đã xác nhận migration và
`alembic check` thành công trên MySQL thật khi triển khai Docker.

## 3. Chạy trên PowerShell

Từ thư mục gốc `C:\Users\Dell\Desktop\LMS`:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r lms-platform/backend/requirements.lock.txt
.venv/Scripts/python -m pip install --no-deps -e lms-platform/backend
Copy-Item lms-platform/backend/.env.example lms-platform/backend/.env
.venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Dán secret vừa tạo vào JWT_SECRET trong `.env`; không commit file này. Nếu máy dùng
certificate store của Windows và pip báo lỗi CA, có thể dùng
`uv --system-certs pip install --python .venv/Scripts/python.exe -e 'lms-platform/backend[dev]'`.

Bật Docker Desktop, sau đó chạy MySQL development (port 3306 phải trống):

```powershell
docker compose -f lms-platform/infrastructure/containers/compose.mysql.yml up -d --wait
Set-Location lms-platform/backend
../../.venv/Scripts/python -m alembic upgrade head
../../.venv/Scripts/python -m alembic check
../../.venv/Scripts/python -m uvicorn src.main:create_app --factory --reload
```

Nếu dùng MySQL có sẵn, DBA tạo database `lms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`
và tài khoản phù hợp rồi cập nhật DATABASE_URL. Production tách tài khoản migration DDL
và tài khoản runtime DML; giới hạn quyền audit, cấu hình TLS MySQL và quản lý secret theo
hạ tầng thực tế. Compose chỉ dành cho phát triển. JWT/RBAC chưa được triển khai ở bản này.

Ứng dụng mở `/docs` trong development; `/healthz` và `/livez` đã được bổ sung khi đóng gói Docker.
Để sinh migration mới sau khi sửa model (chạy từ backend):

```powershell
../../.venv/Scripts/python -m alembic revision --autogenerate -m "describe_change"
# Review revision, đặc biệt ENUM, CHECK, server defaults và thao tác có thể mất dữ liệu.
../../.venv/Scripts/python -m alembic upgrade head
../../.venv/Scripts/python -m alembic check
../../.venv/Scripts/python -m alembic upgrade head --sql
```

Autogenerate không thay thế review; đặc biệt thay đổi enum/check/default cần kiểm tra SQL.
MySQL DDL có implicit commit: migration lỗi giữa chừng có thể để lại schema một phần.
Backup trước triển khai; chỉ downgrade trên database thử nghiệm hoặc theo kế hoạch phục hồi.
SQL snapshot là phương án xem/review, không chạy cả snapshot lẫn upgrade cho cùng database.

## 4. Kiểm thử

Từ backend:

```powershell
../../.venv/Scripts/python -m pytest -q
../../.venv/Scripts/ruff check src tests ../database/migrations
```

Kiểm thử integration cần tài khoản có quyền CREATE/DROP DATABASE; test tự tạo database
`lms_test_<uuid>` và chỉ xóa database đó. Không sửa database ghi trong URL:

```powershell
$env:MYSQL_TEST_ADMIN_URL = 'mysql+aiomysql://root:lms_local_root_password@127.0.0.1:3306/mysql?charset=utf8mb4'
../../.venv/Scripts/python -m pytest -m integration -q
Remove-Item Env:MYSQL_TEST_ADMIN_URL
```

Test này chạy upgrade → check drift → insert Unicode → kiểm tra UNIQUE/FK/CHECK/RESTRICT
→ downgrade → upgrade → check drift. Nếu thiếu biến môi trường, test báo skip rõ ràng.

## Tài liệu chính thức đối chiếu

- [SQLAlchemy AsyncIO](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLAlchemy MySQL, server defaults và ON UPDATE](https://docs.sqlalchemy.org/en/20/dialects/mysql.html)
- [Alembic với asyncio](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
