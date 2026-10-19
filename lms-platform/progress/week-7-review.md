# Review tuần 7 — WBS 7.1–7.4

Checkpoint **19/10/2026** hoàn thành bốn task đầu của tuần 7:

| WBS | Kết quả | Bằng chứng chính |
|---|---|---|
| 7.1 | Baseline endpoint/job | 12 course, 201 learner; p50/p95/max, throughput, SQL/op; 6 budget đạt |
| 7.2 | Queue/retry/idempotency | retry bền, backoff, timeout, restart, concurrent worker/enqueue |
| 7.3 | Cache theo scope | live auth, actor/role/version key, cross-process invalidation, TTL/LRU |
| 7.4 | Scan và storage | clamd INSTREAM fail-closed, quarantine/backfill, digest/path protection |

Chi tiết và lệnh tái lập:

- [Performance](../docs/testing/week-7-performance.md)
- [Background jobs](../docs/testing/week-7-jobs.md)
- [Cache](../docs/testing/week-7-cache.md)
- [Storage](../docs/testing/week-7-storage.md)

Database head là **0015_file_scanning**. Migration phải chạy trước app. Khi nâng
database có file upload cũ, chạy backfill scanner theo batch trước khi mở lại quyền
tải; file cũ bị quarantine mặc định.

Xác minh cuối: **133 backend tests** đạt trên MySQL 8.0 thật, `--require-mysql`,
không skip integration. Ruff, shared-contract drift, progress sync tests, frontend
unit tests và production build đạt. Baseline sau cache đạt toàn bộ budget đã đặt.

Các mục 7.5–7.8 chưa nằm trong checkpoint này.
