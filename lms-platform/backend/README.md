# LMS backend — FastAPI + MySQL, truy vấn SQL thuần

Theo dõi và đồng bộ tiến độ Google Sheet: xem [progress/README.md](../progress/README.md).

Backend dùng **câu SQL viết trực tiếp** cho SELECT/INSERT/UPDATE/DELETE. Không còn
ORM model, `Mapped`, `mapped_column`, relationship hoặc `AsyncSession`.
SQLAlchemy Core chỉ giữ nhiệm vụ connection pool, async connection, bind parameters
và transaction trên driver aiomysql; không xây truy vấn bằng biểu thức ORM/Core.
Alembic tiếp tục quản lý lịch sử schema.

## Checkpoint tuần 1 — 09/09/2026

Đã bổ sung response/error contract, JSON logging/trace ID, JWT/RBAC skeleton,
shared contracts và CI/PR template. Scope/backlog P0/P1/P2 tại
[week-1-scope.md](../docs/architecture/week-1-scope.md).

- `src/core/contracts.py`: SuccessResponse, ErrorResponse, CurrentUser.
- `src/core/errors/handlers.py`: handler 401/403/404/409/422/500 và DB conflicts.
- `src/core/middleware/trace.py`: X-Trace-ID, context riêng mỗi request, log JSON
  method/route template/status/duration; không log token, query string hoặc body.
- `src/core/security/jwt.py`: phát/kiểm access token HS256, iss/aud/time/type/sub/jti.
- `src/core/security/dependencies.py`: `get_current_user` và `require_roles` từ DB.
- `GET /api/v1/auth/me`: trả profile an toàn, role hiện tại; cần Bearer access token.
- `shared/contracts`: TypeScript + JSON Schema/OpenAPI; CI kiểm schema drift.
- `.github/workflows/backend.yml`: lint, MySQL integration/migration và contract checks.

Ví dụ gắn role dependency cho router nghiệp vụ sắp xây:

```python
from fastapi import APIRouter, Depends
from src.core.security.dependencies import require_roles

router = APIRouter(dependencies=[Depends(require_roles(["ADMIN", "INSTRUCTOR"]))])
```

Scope sở hữu course/file/enrollment vẫn phải kiểm tra ở application. Token không chứa
quyền đáng tin; role/account status đọc từ SQL mỗi request. User bị khóa/xóa mềm bị
401; token hợp lệ thiếu role nhận 403. Login/refresh/reset-password là tuần 2, chưa
có endpoint công khai phát token. `create_access_token` chỉ gọi sau xác minh mật khẩu.

Health response hiện dùng envelope, ví dụ:

```json
{"code":"OK","message":"Success","data":{"status":"ok","database":"ok"},"trace_id":"..."}
```

Error response có `{code,message,details,trace_id}`. Header X-Trace-ID khớp body cả
khi lỗi. Header trace đầu vào phải là 1–64 ký tự chữ/số/_/-; sai định dạng sẽ sinh ID mới.
JWT secret chỉ nằm trong environment, không xuất ra schema/log/response.

Sinh/kiểm shared contracts từ repository root:

```powershell
.venv/Scripts/python lms-platform/backend/scripts/export_contracts.py
.venv/Scripts/python lms-platform/backend/scripts/export_contracts.py --check
```

Workflow CI đã được cấu hình; các bước kiểm tra tương ứng chạy local. Chưa có bằng
chứng remote GitHub Actions run khi chưa push. Schema lms vẫn ở 0001_p0, không cần
migration mới cho các thay đổi tuần 1 này.

## 1. Cấu trúc mới

```text
lms-platform/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.runtime.lock.txt
│   ├── requirements.lock.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── src/
│   │   ├── main.py                     # app factory, lifespan, engine disposal
│   │   ├── config/config.py            # Pydantic Settings, URL, JWT config
│   │   ├── core/database/
│   │   │   ├── database.py             # AsyncEngine + get_connection
│   │   │   ├── sql.py                  # execute/fetch_one/fetch_all/insert
│   │   │   ├── health.py               # /livez, /healthz
│   │   │   └── check.py                # CLI SELECT DATABASE()
│   │   └── modules/
│   │       ├── identity_access/infrastructure/repository.py
│   │       ├── user_role/infrastructure/repository.py
│   │       ├── course/infrastructure/repository.py
│   │       ├── learning_content/infrastructure/repository.py
│   │       ├── enrollment/infrastructure/repository.py
│   │       └── audit_security/infrastructure/repository.py
│   └── tests/{unit,integration}/
├── database/
│   ├── migrations/{env.py,script.py.mako,versions/0001_p0.py}
│   └── schemas/shared/0001_p0.sql       # DDL MySQL để xem/review
├── compose.yml
└── infrastructure/scripts/build-backend.ps1
```

Mỗi module giữ bốn tầng: `presentation` nhận request, `application` xử lý use case
và transaction, `domain` chứa business rule/enum thuần Python, `infrastructure`
chứa repository SQL. `repository.py` là nơi đọc/sửa câu truy vấn của module đó.

## 2. Viết truy vấn SQL thuần

Ví dụ thực tế trong `IdentityRepository.get_credentials`:

```python
return await self.fetch_one(
    """SELECT id, email, username, hashed_password, status
       FROM users WHERE email = :email AND deleted_at IS NULL""",
    {"email": email},
)
```

`SqlRepository` chuyển SQL qua `text(sql)` và gửi tham số riêng vào connection.
`:email` được driver bind; không nối chuỗi hoặc dùng f-string với dữ liệu request.
Tên bảng/cột/ORDER BY phải là hằng số do developer định nghĩa hoặc chọn từ whitelist;
không thể dùng bind parameter thay cho tên cột. Các query hiện có dùng projection
cột rõ ràng, không dùng `SELECT *`.

- `fetch_one`: trả `dict[str, Any] | None`.
- `fetch_all`: trả danh sách dictionary.
- `insert`: trả AUTO_INCREMENT ID từ cursor của chính lệnh INSERT.
- `execute`: trả số dòng matched/affected theo driver. Không tự commit.

Dictionary trả về là snapshot dữ liệu; sửa dictionary **không** ghi xuống database.
Muốn sửa dữ liệu phải thực hiện câu `UPDATE` rõ ràng. Đây là khác biệt chính với ORM.
`get_credentials` chỉ dùng nội bộ xác thực; không trả hash ra API. `get_user` không
chọn cột password hash. Truy vấn danh sách course có giới hạn tối đa 100 bản ghi.

## 3. Transaction

Ví dụ một đơn vị ghi dữ liệu nguyên tử sau khi application đã kiểm tra quyền:

```python
from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.course.infrastructure.repository import CourseRepository


async def persist_authorized_course(
    engine: AsyncEngine, *, actor_id: int, code: str, title: str, trace_id: str
) -> int:
    async with engine.begin() as connection:
        course_id = await CourseRepository(connection).create(
            code=code, title=title, created_by=actor_id
        )
        await AuditRepository(connection).append_log(
            actor_id=actor_id,
            action="course.create",
            resource="course",
            resource_id=str(course_id),
            trace_id=trace_id,
        )
    # COMMIT đã hoàn thành trước khi trả kết quả. Exception sẽ ROLLBACK cả hai lệnh.
    return course_id
```

FastAPI có `ConnectionDependency` / `get_connection`. Dependency cấp một connection
cho request và rollback phần chưa commit khi đóng. Với write use case, gọi
`async with connection.begin()` **trước truy vấn đầu tiên**, hoặc commit/rollback
tường minh transaction đã được auth dependency bắt đầu. SELECT cũng có thể autobegin;
không lồng `begin()` vào transaction đã mở. Không chia sẻ connection giữa nhiều
coroutine chạy đồng thời. Repository không commit để application có thể gộp nhiều
repository trong một transaction.

Refresh token lookup có `FOR UPDATE`: giữ transaction xuyên suốt lookup/check/rotation.
Course/enrollment update dùng `WHERE status = :expected` để phát hiện thay đổi đồng thời;
application quyết định transition nào được phép. FK/UNIQUE/CHECK vẫn do MySQL thực thi.

## 4. Phạm vi repository P0

| Repository | Bảng và thao tác nền tảng |
|---|---|
| IdentityRepository | users: tạo/đọc/status/soft delete; refresh_tokens: lưu, khóa đọc, revoke family |
| RoleRepository | roles, permissions, user_roles, role_permissions: tạo/gán/đọc quyền |
| CourseRepository | courses: tạo draft, đọc, list theo status, đổi status, soft delete |
| ContentRepository | modules, lessons, lesson_resources: tạo, đọc lesson và resource |
| EnrollmentRepository | enrollments: tạo pending, đọc, đổi status; course_staff: phân công |
| AuditRepository | audit_logs, security_events: append bằng INSERT, JSON serialize rõ ràng |

Đây là các **primitive truy cập dữ liệu**, chưa phải API nghiệp vụ hoàn chỉnh.
JWT/RBAC skeleton và error contract đã có. Login/logout flow, validation nghiệp vụ,
course publish policy và enrollment eligibility là phần tiếp theo. Không đưa thẳng
repository ra route công khai mà thiếu kiểm tra quyền và business rule.

Các query nội dung đã lọc `deleted_at IS NULL` cho lesson, module và course.
Role/permission lookup chỉ trả quyền cho user ACTIVE, chưa soft delete.
Quyền học vẫn cần kiểm tra `course=PUBLISHED` và `enrollment=ACTIVE` tại application.

## 5. Schema và migration

**14 bảng nghiệp vụ và dữ liệu trong database `lms` được giữ nguyên** khi đổi tầng query.
Schema dùng MySQL 8.0.16+ (CHECK được thực thi), InnoDB, utf8mb4_unicode_ci,
`BIGINT UNSIGNED AUTO_INCREMENT`, `created_at`/`updated_at DATETIME(6)` UTC.
`updated_at` tự cập nhật tại MySQL nên SQL trực tiếp vẫn có tracking.

Enum domain hiện có: user ACTIVE/INACTIVE/LOCKED; course DRAFT/PUBLISHED/ARCHIVED;
enrollment PENDING/ACTIVE/SUSPENDED/COMPLETED. CHECK ràng buộc completed_at chỉ có khi
COMPLETED. UNIQUE student-course, email, username và code vẫn được giữ.
FK dùng RESTRICT; soft delete giữ chỗ unique email/code/position. Audit không soft delete.
Nhật ký append-only cần quyền DB phù hợp; không đưa password/token vào details JSON.
Datetime truyền từ application phải là UTC không tzinfo, phù hợp MySQL DATETIME.

Revision `0001_p0.py` đã áp dụng nên giữ nguyên như lịch sử. File này dùng Alembic
schema operations (không phải ORM, không import application model). Không sửa lịch sử
chỉ để thay cách biểu diễn DDL. Có thể xem toàn bộ câu CREATE TABLE/INDEX thuần trong
`database/schemas/shared/0001_p0.sql` hoặc lệnh xuất SQL bên dưới.

Từ nay tạo migration thủ công và viết SQL rõ ràng:

```powershell
# Chạy tại backend
../../.venv/Scripts/python -m alembic revision -m "describe_schema_change"
```

```python
from alembic import op

# Giữ revision/down_revision được Alembic sinh trong file.
def upgrade() -> None:
    op.execute("ALTER TABLE courses ADD COLUMN summary VARCHAR(500) NULL")

def downgrade() -> None:
    op.execute("ALTER TABLE courses DROP COLUMN summary")
```

Đây chỉ là ví dụ, chưa thêm cột `summary` vào schema. Mỗi `op.execute` chứa một statement;
không split SQL tùy tiện bằng dấu `;` khi có stored procedure/chuỗi literal.

```powershell
../../.venv/Scripts/python -m alembic upgrade head
../../.venv/Scripts/python -m alembic current
../../.venv/Scripts/python -m alembic upgrade head --sql
```

Không dùng `revision --autogenerate` hoặc `alembic check`: hai lệnh này phụ thuộc model
metadata, vốn đã được loại bỏ. `current` chỉ xác nhận revision, **không** chứng minh
schema không drift. Xác minh DDL bằng review SQL/SHOW CREATE TABLE và integration test.
MySQL DDL implicit commit; backup trước thay đổi schema thật và chỉ thử downgrade
trên database thử nghiệm. Không chạy snapshot SQL rồi chạy lại migration trên cùng DB.

## 6. Chạy local và Docker

`.env` giữ DATABASE_URL `mysql+aiomysql://.../lms?charset=utf8mb4` và JWT_SECRET hiện có.
Không commit secret; percent-encode ký tự đặc biệt trong username/password. Không bọc
giá trị `.env` trong dấu nháy vì Compose dùng `format: raw`. Yêu cầu Compose 2.30+.
DB_HOST_OVERRIDE=host.docker.internal chỉ áp dụng trong container; Python local dùng
host trong DATABASE_URL. Pool có pre-ping, recycle, giới hạn size, timeout, UTC và strict mode.

Từ thư mục gốc repository, nếu chưa cài môi trường:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r lms-platform/backend/requirements.lock.txt
.venv/Scripts/python -m pip install --no-deps -e lms-platform/backend
```

Từ `lms-platform/backend`:

```powershell
../../.venv/Scripts/python -m src.core.database.check
../../.venv/Scripts/python -m uvicorn src.main:create_app --factory --reload --port 8002 --no-access-log
```

Từ `lms-platform` với Docker Desktop và MySQL80 đang chạy:

```powershell
docker compose build
# Nếu mạng Windows cần CA riêng khi pip tải dependency:
# ./infrastructure/scripts/build-backend.ps1 -UseWindowsCertificates
docker compose run --rm --no-deps api python -m src.core.database.check
docker compose run --rm migrate
docker compose run --rm migrate python -m alembic current
docker compose up -d --wait api
docker compose ps
Invoke-RestMethod http://localhost:8001/healthz
```

Cổng Docker mặc định 8001 vì 8000 đã có ứng dụng khác dùng. Đặt `$env:LMS_API_PORT`
để đổi cổng. `/docs` bật ở development; `/livez` kiểm tra API; `/healthz` SELECT 1,
trả 503 khi database không sẵn sàng. Container dùng user không root, filesystem chỉ đọc,
log rotation và bind API vào localhost. `.env` không nằm trong image.
MySQL vẫn chạy trên Windows; không cần chạy Compose MySQL development cũ.

Nếu tải dependency trong Docker bị chậm/timeout, có thể tải wheel bằng mạng Windows
rồi build offline (Python 3.11, Linux amd64, từ `lms-platform`):

```powershell
./infrastructure/scripts/download-backend-wheels.ps1
docker compose build
```

Wheel lưu tại `backend/.wheels`, bị Git bỏ qua. Docker mount từ build stage riêng
và cài theo phiên bản trong lock file, không chứa thư mục wheel trong runtime image.
Khi chưa có wheel, Docker vẫn hỗ trợ tải online với timeout 120 giây. Khi đổi lock
file, tải bổ sung wheel trước khi build offline. Không dùng wheel amd64 cho image ARM.

Nếu máy đã có image LMS đúng baseline dependency, có thể tái sử dụng runtime đó:

```powershell
docker compose build --build-arg RUNTIME_BASE=lms-backend:local
```

Build vẫn kiểm tra phiên bản theo lock file và `pip check`, xóa source cũ trong image
rồi copy source mới. Mặc định vẫn build từ `python:3.11-slim-bookworm`. Chỉ dùng wheel
bổ sung từng phần khi tái sử dụng runtime đã có; clean build offline cần đủ bộ wheel.

```powershell
docker compose logs --tail 100 api
docker compose stop api
docker compose down
```

## 7. Kiểm thử

```powershell
# Từ backend
../../.venv/Scripts/python -m pytest -q
../../.venv/Scripts/ruff check src tests ../database/migrations
```

Integration cần `MYSQL_TEST_ADMIN_URL` với tài khoản có quyền CREATE/DROP DATABASE.
Test chỉ tạo và xóa database ngẫu nhiên `lms_test_<uuid>`, không sửa `lms` hoặc database
ghi trong URL. Không đặt mật khẩu thật vào lịch sử shell; có thể lấy biến này qua
secret/environment manager trước khi chạy test.

Integration kiểm tra migration upgrade/downgrade, storage engine/collation, UNIQUE/FK/CHECK,
toàn bộ repository P0, input chứa SQL injection, Unicode/JSON, lastrowid, soft delete,
role lookup, token revoke và rollback nhiều repository. Unit test chặn ORM import trở lại.
Thiếu biến test URL thì integration skip rõ ràng.

## Tài liệu đối chiếu

- [SQLAlchemy: SQL text và transaction](https://docs.sqlalchemy.org/en/20/tutorial/dbapi_transactions.html)
- [Alembic: execute SQL trong migration](https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.execute)
- [Docker Desktop: host.docker.internal](https://docs.docker.com/desktop/features/networking/networking-how-tos/)
