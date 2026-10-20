# WBS 7.7 — Backup/restore rehearsal

`infrastructure/scripts/backup_restore.py` creates a logical MySQL backup with a
single-transaction dump, writes a SHA-256 manifest, verifies the digest, and
restores only to a database named `lms_restore_*`. The source password is passed
through `MYSQL_PWD`; it is never placed in command arguments or logs.

Rehearsal:

```powershell
$env:DATABASE_URL = "mysql+aiomysql://user:password@127.0.0.1:3306/lms?charset=utf8mb4"
python infrastructure/scripts/backup_restore.py backup --output .local-logs/lms.sql
python infrastructure/scripts/backup_restore.py verify --file .local-logs/lms.sql
python infrastructure/scripts/backup_restore.py restore --file .local-logs/lms.sql --target-database lms_restore_week7
```

After restoring, run `alembic current`, `src.core.database.check` against the
restore URL and the smoke queries in the release runbook. Delete the disposable
restore database after recording row counts and the manifest checksum.
