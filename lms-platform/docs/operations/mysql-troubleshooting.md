# MySQL Workbench connection

The LMS uses the Windows MySQL service and the `lms` schema. In Workbench use:

- Hostname: `127.0.0.1`
- Port: `3306`
- Username: the user in `backend/.env` (the local file normally uses `root`)
- Password: the matching password from `DATABASE_URL`
- Default schema: `lms`

The password must be supplied in Workbench; an empty password produces error
1045. If the service is stopped, start **MySQL80** from `services.msc` and retry.
Then run `backend/.venv`'s `python -m src.core.database.check` from
`lms-platform/backend`. It validates the same URL without printing credentials.

If Workbench reports a missing database, create the schema or run the migration
from `lms-platform/backend`:

```powershell
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

Do not publish the `.env` file or paste its password into Git, issue trackers or
chat. The project is configured and verified against `127.0.0.1:3306/lms`.
