"""Grade projections and immutable revision records; caller owns the transaction."""

import json

from src.core.database.sql import SqlRepository
from src.modules.audit_security.infrastructure.repository import AuditRepository


class GradeRepository(SqlRepository):
    async def detail(self, id):
        row = await self.fetch_one(
            "SELECT * FROM gradebook_entries WHERE id=:id FOR UPDATE", {"id": id}
        )
        row["items"] = await self.fetch_all(
            """SELECT item_key,label,score,max_score,feedback FROM grade_items
            WHERE grade_id=:id ORDER BY id FOR UPDATE""",
            {"id": id},
        )
        return row

    async def record(self, id, action, actor_id, trace_id, reason=None):
        row = await self.detail(id)
        await self.insert(
            """INSERT INTO grade_history(grade_id,version,action,actor_id,reason,snapshot)
            VALUES (:id,:version,:action,:actor,:reason,:snapshot)""",
            {
                "id": id,
                "version": row["version"],
                "action": action,
                "actor": actor_id,
                "reason": reason,
                "snapshot": json.dumps(row, default=str, ensure_ascii=False),
            },
        )
        await AuditRepository(self.connection).append_log(
            actor_id=actor_id,
            action="grade." + action.lower(),
            resource="grade",
            resource_id=str(id),
            trace_id=trace_id,
            details={"version": row["version"], "reason": reason},
        )
        return row

    async def replace_items(self, id, items):
        await self.execute("DELETE FROM grade_items WHERE grade_id=:id", {"id": id})
        for item in items:
            await self.insert(
                """INSERT INTO grade_items(grade_id,item_key,label,score,max_score,feedback)
                VALUES (:id,:item_key,:label,:score,:max_score,:feedback)""",
                {"id": id, "feedback": None, **item},
            )
