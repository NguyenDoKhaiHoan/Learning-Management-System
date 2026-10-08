"""Read and acknowledge per-user in-app notifications."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.notification.infrastructure.repository import NotificationRepository

router = APIRouter(
    prefix="/api/v1/notifications", tags=["Notifications"], responses=ERROR_RESPONSES
)


class NotificationPage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    items: list[dict]
    total: int
    unread: int
    limit: int
    offset: int


def result(request: Request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.get("", response_model=SuccessResponse[NotificationPage])
async def list_notifications(
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    repo = NotificationRepository(connection)
    params = {"recipient": int(user.id), "limit": limit, "offset": offset}
    unread_filter = " AND is_read=0" if unread_only else ""
    items = await repo.fetch_all(
        """SELECT id,type,title,body,course_id,resource_type,resource_id,is_read,created_at,read_at
           FROM notifications WHERE recipient_id=:recipient"""
        + unread_filter
        + " ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset",
        params,
    )
    for item in items:
        item["id"] = str(item["id"])
        if item["resource_id"] is not None:
            item["resource_id"] = str(item["resource_id"])
        if item["course_id"] is not None:
            item["course_id"] = str(item["course_id"])
    total_row = await repo.fetch_one(
        "SELECT COUNT(*) AS count FROM notifications WHERE recipient_id=:recipient" + unread_filter,
        {"recipient": int(user.id)},
    )
    return result(
        request,
        NotificationPage(
            items=items,
            total=int(total_row["count"] if total_row else 0),
            unread=await repo.unread_count(int(user.id)),
            limit=limit,
            offset=offset,
        ).model_dump(),
    )


@router.patch("/{notification_id}/read", response_model=SuccessResponse[dict])
async def mark_read(
    notification_id: int,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    repo = NotificationRepository(connection)
    await repo.execute(
        """UPDATE notifications SET is_read=1,read_at=UTC_TIMESTAMP(6)
           WHERE id=:id AND recipient_id=:recipient""",
        {"id": notification_id, "recipient": int(user.id)},
    )
    await connection.commit()
    return result(request, {"id": str(notification_id), "is_read": True})


@router.get("/unread-count", response_model=SuccessResponse[dict])
async def unread_count(
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    count = await NotificationRepository(connection).unread_count(int(user.id))
    return result(request, {"unread": count})


@router.post("/read-all", response_model=SuccessResponse[dict])
async def mark_all_read(
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    repo = NotificationRepository(connection)
    count = await repo.execute(
        """UPDATE notifications SET is_read=1,read_at=UTC_TIMESTAMP(6)
           WHERE recipient_id=:recipient AND is_read=0""",
        {"recipient": int(user.id)},
    )
    await connection.commit()
    return result(request, {"updated": count})
