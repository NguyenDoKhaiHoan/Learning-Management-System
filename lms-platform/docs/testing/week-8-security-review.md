# WBS 8.4 — Security review trước phát hành

Security review local ngày **22/10/2026** bao phủ authentication, authorization,
IDOR, private files/exports, secret handling và production configuration. Review dùng
security regression hiện có và policy checker mới; không coi một file tồn tại là bằng
chứng bảo mật.

## Checklist kiểm soát

| Mục | Kiểm soát | Bằng chứng |
| --- | --- | --- |
| AuthN | JWT signature/issuer/audience/expiry/type, refresh rotation, account status | `test_week6_access_security.py`, regression tuần 2 |
| AuthZ/IDOR | DB role làm nguồn quyền; resource scope cho course, attempt, submission, grade, export | 51 request bị từ chối và các case ownership trong `test_week6_access_security.py` |
| File/private response | containment, MIME/size, scan fail-closed, no-store/nosniff, live scope khi download | `test_week6_access_security.py`, `test_week7_storage.py` |
| Secrets | Không track `.env`, `.secrets`, private key; log/HTTP không lộ credential | `security_review.py`, trace/log sanitization tests |
| Production config | Production bắt buộc clamd; email bật phải dùng STARTTLS | `security_review.py` policy assertions |
| Audit/observability | Publish, permission, grade, submission và security event có actor/resource/trace | `test_week6_audit.py`, `test_week6_security.py`, `/metrics` low-cardinality |

## Chạy lại

Từ `lms-platform`, chạy policy checker:

```powershell
../.venv/Scripts/python.exe infrastructure/scripts/security_review.py
```

Với MySQL disposable, chạy cả security regression:

```powershell
$env:MYSQL_TEST_ADMIN_URL = "mysql+aiomysql://..."
../.venv/Scripts/python.exe infrastructure/scripts/security_review.py --run-tests
```

Checkpoint local: policy checks đạt; security marker **7 passed**. Full acceptance/security
subset đạt **11 passed**. Không có file secret-like nào được Git track.

## Điều kiện trước production

Secret manager phải cung cấp database URL, JWT secret và SMTP secret; clamd phải sẵn
sàng trước khi mở upload. Bật rate limiting, dependency/pentest scan và giám sát alert
ở hạ tầng triển khai là công việc vận hành tiếp theo, không được suy ra từ các test ứng
dụng này. Nếu một điều kiện production không đạt, deployment phải dừng tại health gate.
