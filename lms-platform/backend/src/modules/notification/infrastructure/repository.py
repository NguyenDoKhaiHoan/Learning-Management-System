from src.core.database.sql import SqlRepository


class NotificationRepository(SqlRepository):
    async def create(
        self,
        *,
        recipient_id: int,
        course_id: int | None = None,
        type: str,
        title: str,
        body: str,
        resource_type: str | None = None,
        resource_id: int | str | None = None,
    ) -> int:
        return await self.insert(
            """INSERT INTO notifications
               (recipient_id,course_id,type,title,body,resource_type,resource_id)
               VALUES (:recipient,:course,:type,:title,:body,:resource_type,:resource_id)""",
            {
                "recipient": recipient_id,
                "course": course_id,
                "type": type,
                "title": title,
                "body": body,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )

    async def unread_count(self, recipient_id: int) -> int:
        row = await self.fetch_one(
            "SELECT COUNT(*) AS count FROM notifications "
            "WHERE recipient_id=:recipient AND is_read=0",
            {"recipient": recipient_id},
        )
        return int(row["count"] if row else 0)


async def notify(
    connection,
    recipient_id: int,
    *,
    type: str,
    title: str,
    body: str,
    resource_type: str | None = None,
    resource_id: int | str | None = None,
) -> int:
    """Queue an in-app notification in the caller's transaction."""
    return await NotificationRepository(connection).create(
        recipient_id=recipient_id,
        type=type,
        title=title,
        body=body,
        resource_type=resource_type,
        resource_id=resource_id,
    )
