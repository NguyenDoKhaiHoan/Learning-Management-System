# Review tuần 8 — WBS 8.1–8.4

Checkpoint **22/10/2026** hoàn thành bốn task đầu tuần 8:

| WBS | Kết quả | Bằng chứng chính |
|---|---|---|
| 8.1 | UAT ba vai trò | `docs/testing/week-8-uat.md`; 12 browser UAT tests, 11 backend acceptance/security tests |
| 8.2 | Docs kiến trúc/API/business rules/workflow | `docs/architecture/system-overview.md`, `docs/api/current.md`, access matrix và user journeys |
| 8.3 | Deployment rehearsal | `infrastructure/scripts/deployment_rehearsal.py`; MySQL disposable, migration head `0017_forum_moderation`, seed counts và cleanup |
| 8.4 | Security review trước phát hành | `infrastructure/scripts/security_review.py`; policy checks và 7 security tests |

## Xác minh tại checkpoint

- Frontend unit: **11 passed**.
- Frontend production build: **thành công**.
- Browser UAT: **12 passed** trên Chromium, gồm Admin/Instructor/Student, desktop/mobile,
  role guard, assessment, audit/security và report/export.
- Backend acceptance/security subset trên MySQL 8.0 thật: **11 passed**, 125 test khác
  được loại khỏi subset.
- Security marker riêng: **7 passed**.
- Progress sync tests: **5 passed**.
- Deployment rehearsal: migration/seed/drop disposable database đạt.

Các task 8.5–8.7 vẫn giữ nguyên trạng thái theo dõi hiện tại; bản review này chỉ cập
nhật WBS 8.1–8.4.
