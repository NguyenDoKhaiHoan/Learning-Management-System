"""Basic course-scoped discussion forum API."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.course.presentation.router import Id, Read, Write
from src.modules.forum_messaging.application.service import ForumService

router = APIRouter(
    prefix="/api/v1/courses/{course_id}/forum", tags=["Forum"], responses=ERROR_RESPONSES
)


class ForumOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    id: str
    course_id: str
    title: str
    description: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class ThreadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=16000)


class ReplyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    body: str = Field(min_length=1, max_length=16000)


class ThreadOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    id: str
    forum_id: str
    course_id: str
    author_id: str
    author_username: str
    title: str
    body: str
    status: str
    reply_count: int = 0
    created_at: datetime
    updated_at: datetime


class MessageOutput(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    id: str
    thread_id: str
    author_id: str
    author_username: str
    body: str
    hidden: bool = False
    created_at: datetime
    updated_at: datetime


class MessagePage(BaseModel):
    items: list[MessageOutput]
    total: int
    limit: int
    offset: int


class ThreadDetail(ThreadOutput):
    messages: list[MessageOutput] = Field(default_factory=list)


class Page(BaseModel):
    items: list[ThreadOutput]
    total: int
    limit: int
    offset: int


class ModerationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    action: Literal["OPEN", "LOCKED", "ARCHIVED", "HIDE", "RESTORE"]
    reason: str | None = Field(default=None, max_length=500)


class MembershipRequestInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


class MembershipReviewInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    status: Literal["APPROVED", "REJECTED"]
    reason: str | None = Field(default=None, max_length=500)


def result(request: Request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


async def _ensure_forum(service: ForumService, course_id: int):
    forum = await service.forum(course_id, create=True)
    if forum is None:
        raise HTTPException(404, "Forum chưa được khởi tạo")
    return forum


@router.get("", dependencies=Read, response_model=SuccessResponse[ForumOutput])
@router.get(
    "/", include_in_schema=False, dependencies=Read, response_model=SuccessResponse[ForumOutput]
)
async def get_forum(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    service = ForumService(connection, user, request.state.trace_id)
    forum = await service.get_forum_or_404(course_id)
    await connection.commit()
    return result(request, forum)


@router.get("/threads", dependencies=Read, response_model=SuccessResponse[Page])
async def list_threads(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    service = ForumService(connection, user, request.state.trace_id)
    forum = await service.get_forum_or_404(course_id)
    await connection.commit()
    total = await service.repo.fetch_one(
        "SELECT COUNT(*) AS total FROM threads WHERE forum_id=:forum AND status <> 'ARCHIVED'",
        {"forum": forum["id"]},
    )
    rows = await service.repo.fetch_all(
        """SELECT t.id, t.forum_id, :course AS course_id, t.author_id,
                  u.username AS author_username, t.title, t.body, t.status,
                  COUNT(m.id) AS reply_count, t.created_at, t.updated_at
           FROM threads t JOIN users u ON u.id=t.author_id
           LEFT JOIN messages m ON m.thread_id=t.id AND m.deleted_at IS NULL
           WHERE t.forum_id=:forum AND t.status <> 'ARCHIVED'
           GROUP BY t.id, t.forum_id, t.author_id, u.username, t.title, t.body,
                    t.status, t.created_at, t.updated_at
           ORDER BY t.updated_at DESC, t.id DESC LIMIT :limit OFFSET :offset""",
        {"course": course_id, "forum": forum["id"], "limit": limit, "offset": offset},
    )
    return result(request, Page(items=rows, total=total["total"], limit=limit, offset=offset))


@router.post("/threads", dependencies=Read, status_code=201,
             response_model=SuccessResponse[ThreadOutput])
async def create_thread(
    course_id: Id,
    body: ThreadInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ForumService(connection, user, request.state.trace_id)
    forum = await _ensure_forum(service, course_id)
    thread_id = await service.repo.insert(
        """INSERT INTO threads (forum_id, author_id, title, body)
           VALUES (:forum, :author, :title, :body)""",
        {"forum": forum["id"], "author": int(user.id), **body.model_dump()},
    )
    await service.audit("forum.thread.create", "thread", thread_id)
    await connection.commit()
    return result(request, await service.get_thread(course_id, thread_id))


@router.get("/threads/{thread_id}", dependencies=Read, response_model=SuccessResponse[ThreadDetail])
async def read_thread(
    course_id: Id,
    thread_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ForumService(connection, user, request.state.trace_id)
    thread = await service.get_thread(course_id, thread_id)
    if thread is None or thread["status"] == "ARCHIVED":
        raise HTTPException(404)
    messages = await service.repo.fetch_all(
        """SELECT m.id, m.thread_id, m.author_id, u.username AS author_username,
                  m.body, m.created_at, m.updated_at
           FROM messages m JOIN users u ON u.id=m.author_id
           JOIN threads t ON t.id=m.thread_id JOIN forums f ON f.id=t.forum_id
           WHERE m.thread_id=:thread AND f.course_id=:course AND m.deleted_at IS NULL
           ORDER BY m.created_at, m.id""",
        {"thread": thread_id, "course": course_id},
    )
    return result(request, ThreadDetail(messages=messages, **thread))


@router.get("/moderation/threads/{thread_id}", dependencies=Write,
            response_model=SuccessResponse[ThreadDetail])
async def review_thread(
    course_id: Id, thread_id: Id, request: Request,
    connection: ConnectionDependency, user: CurrentUserDependency,
):
    service = ForumService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True)
    thread = await service.get_thread(course_id, thread_id, write=True)
    if thread is None:
        raise HTTPException(404)
    messages = await service.repo.fetch_all(
        """SELECT m.id,m.thread_id,m.author_id,u.username AS author_username,m.body,
                  m.deleted_at IS NOT NULL AS hidden,m.created_at,m.updated_at
           FROM messages m JOIN users u ON u.id=m.author_id
           WHERE m.thread_id=:thread ORDER BY m.created_at,m.id LIMIT 100""",
        {"thread": thread_id},
    )
    return result(request, ThreadDetail(messages=messages, **thread))


@router.get("/moderation/messages", dependencies=Write,
            response_model=SuccessResponse[MessagePage])
async def hidden_messages(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    service = ForumService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True)
    where = """FROM messages m JOIN threads t ON t.id=m.thread_id
               JOIN forums f ON f.id=t.forum_id JOIN users u ON u.id=m.author_id
               WHERE f.course_id=:course AND m.deleted_at IS NOT NULL"""
    params = {"course": course_id, "limit": limit, "offset": offset}
    rows = await service.repo.fetch_all(
        """SELECT m.id,m.thread_id,m.author_id,u.username AS author_username,m.body,
                  TRUE AS hidden,m.created_at,m.updated_at """ + where
        + " ORDER BY m.moderated_at DESC,m.id DESC LIMIT :limit OFFSET :offset", params,
    )
    total = await service.repo.fetch_one("SELECT COUNT(*) AS total " + where, params)
    return result(request, MessagePage(
        items=rows, total=total["total"], limit=limit, offset=offset,
    ))


@router.get("/membership/me", dependencies=Read, response_model=SuccessResponse[dict | None])
async def my_membership(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    row = await ForumService(connection, user, request.state.trace_id).repo.fetch_one(
        """SELECT status,reason,reviewed_at FROM forum_membership_requests
           WHERE course_id=:course AND user_id=:user""",
        {"course": course_id, "user": int(user.id)},
    )
    return result(request, row)


@router.post(
    "/threads/{thread_id}/messages",
    dependencies=Read,
    status_code=201,
    response_model=SuccessResponse[MessageOutput],
)
async def create_reply(
    course_id: Id,
    thread_id: Id,
    body: ReplyInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ForumService(connection, user, request.state.trace_id)
    thread = await service.get_thread(course_id, thread_id, write=True)
    if thread is None or thread["status"] == "ARCHIVED":
        raise HTTPException(404)
    if thread["status"] == "LOCKED":
        raise HTTPException(409, "Thread đã bị khóa")
    message_id = await service.repo.insert(
        """INSERT INTO messages (thread_id, author_id, body)
           VALUES (:thread, :author, :body)""",
        {"thread": thread_id, "author": int(user.id), "body": body.body},
    )
    await service.audit("forum.message.create", "message", message_id)
    await connection.commit()
    message = await service.repo.fetch_one(
        """SELECT m.id, m.thread_id, m.author_id, u.username AS author_username,
                  m.body, m.created_at, m.updated_at
           FROM messages m JOIN users u ON u.id=m.author_id WHERE m.id=:id""",
        {"id": message_id},
    )
    return result(request, message)


@router.post(
    "/threads/{thread_id}/moderate",
    dependencies=Write,
    response_model=SuccessResponse[ThreadOutput],
)
async def moderate_thread(
    course_id: Id,
    thread_id: Id,
    body: ModerationInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ForumService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True)
    thread = await service.get_thread(course_id, thread_id, write=True)
    if thread is None:
        raise HTTPException(404)
    if body.action in {"HIDE", "RESTORE"}:
        raise HTTPException(422, "Thread moderation action must be OPEN, LOCKED or ARCHIVED")
    await service.repo.execute(
        """UPDATE threads SET status=:status,moderation_reason=:reason,
           moderated_by=:actor,moderated_at=UTC_TIMESTAMP(6) WHERE id=:id""",
        {
            "status": body.action,
            "reason": body.reason,
            "actor": int(user.id),
            "id": thread_id,
        },
    )
    await service.audit(
        "forum.thread.moderate",
        "thread",
        thread_id,
        details={"action": body.action, "reason": body.reason},
    )
    await connection.commit()
    return result(request, await service.get_thread(course_id, thread_id))


@router.post(
    "/threads/{thread_id}/messages/{message_id}/moderate",
    dependencies=Write,
    response_model=SuccessResponse[MessageOutput],
)
async def moderate_message(
    course_id: Id,
    thread_id: Id,
    message_id: Id,
    body: ModerationInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ForumService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True)
    message = await service.repo.fetch_one(
        """SELECT m.id,m.thread_id,m.author_id,u.username AS author_username,m.body,
                  m.created_at,m.updated_at FROM messages m
           JOIN users u ON u.id=m.author_id JOIN threads t ON t.id=m.thread_id
           JOIN forums f ON f.id=t.forum_id
           WHERE m.id=:message AND m.thread_id=:thread AND f.course_id=:course""",
        {"message": message_id, "thread": thread_id, "course": course_id},
    )
    if message is None:
        raise HTTPException(404)
    if body.action not in {"HIDE", "RESTORE"}:
        raise HTTPException(422, "Message moderation action must be HIDE or RESTORE")
    await service.repo.execute(
        """UPDATE messages SET deleted_at=IF(:hide=1,UTC_TIMESTAMP(6),NULL),
           moderation_reason=:reason,
           moderated_by=:actor,moderated_at=UTC_TIMESTAMP(6) WHERE id=:id""",
        {
            "hide": body.action == "HIDE",
            "reason": body.reason,
            "actor": int(user.id),
            "id": message_id,
        },
    )
    await service.audit(
        "forum.message.moderate",
        "message",
        message_id,
        details={"action": body.action, "reason": body.reason},
    )
    await connection.commit()
    message["hidden"] = body.action == "HIDE"
    return result(request, message)


@router.get("/moderation/queue", dependencies=Write, response_model=SuccessResponse[Page])
async def moderation_queue(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    service = ForumService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True)
    forum_row = await service.repo.fetch_one(
        "SELECT id FROM forums WHERE course_id=:course", {"course": course_id}
    )
    if forum_row is None:
        return result(request, Page(items=[], total=0, limit=limit, offset=offset))
    rows = await service.repo.fetch_all(
        """SELECT t.id,t.forum_id,:course AS course_id,t.author_id,u.username AS author_username,
                  t.title,t.body,t.status,0 AS reply_count,t.created_at,t.updated_at
           FROM threads t JOIN users u ON u.id=t.author_id
           WHERE t.forum_id=:forum AND t.status<>'OPEN'
           ORDER BY t.moderated_at DESC,t.id DESC LIMIT :limit OFFSET :offset""",
        {"course": course_id, "forum": forum_row["id"], "limit": limit, "offset": offset},
    )
    total = await service.repo.fetch_one(
        "SELECT COUNT(*) AS total FROM threads WHERE forum_id=:forum AND status<>'OPEN'",
        {"forum": forum_row["id"]},
    )
    return result(request, Page(items=rows, total=int(total["total"]), limit=limit, offset=offset))


@router.post(
    "/membership-requests", dependencies=Read, status_code=201,
    response_model=SuccessResponse[dict]
)
async def request_membership(
    course_id: Id,
    body: MembershipRequestInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ForumService(connection, user, request.state.trace_id)
    course = await service.repo.fetch_one(
        "SELECT id,status FROM courses WHERE id=:id AND deleted_at IS NULL",
        {"id": course_id},
    )
    if course is None:
        raise HTTPException(404)
    if course["status"] != "PUBLISHED":
        raise HTTPException(409, "Forum membership is available only for published courses")
    await service.repo.fetch_one(
        "SELECT id FROM courses WHERE id=:id FOR UPDATE", {"id": course_id}
    )
    previous = await service.repo.fetch_one(
        """SELECT id,status FROM forum_membership_requests
           WHERE course_id=:course AND user_id=:user FOR UPDATE""",
        {"course": course_id, "user": int(user.id)},
    )
    if previous:
        # Only a manager can change a rejection/approval. Resubmission must not
        # bypass a moderator decision by resetting it to PENDING.
        raise HTTPException(409)
    request_id = await service.repo.insert(
        """INSERT INTO forum_membership_requests(course_id,user_id,reason)
           VALUES (:course,:user,:reason)""",
        {"course": course_id, "user": int(user.id), "reason": body.reason},
    )
    await service.audit(
        "forum.membership.request",
        "forum_membership_request",
        request_id,
        details={"course_id": course_id},
    )
    await connection.commit()
    row = await service.repo.fetch_one(
        """SELECT id,course_id,user_id,status,reason,reviewed_by,reviewed_at,created_at,updated_at
           FROM forum_membership_requests WHERE id=:id""",
        {"id": request_id},
    )
    return result(request, row)


@router.get("/membership-requests", dependencies=Write,
            response_model=SuccessResponse[list[dict]])
async def list_membership_requests(
    course_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    status: Literal["PENDING", "APPROVED", "REJECTED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    service = ForumService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True)
    rows = await service.repo.fetch_all(
        """SELECT r.id,r.course_id,r.user_id,u.username,r.status,r.reason,r.reviewed_by,
                  r.reviewed_at,r.created_at,r.updated_at FROM forum_membership_requests r
           JOIN users u ON u.id=r.user_id WHERE r.course_id=:course
             AND (:status IS NULL OR r.status=:status) ORDER BY r.created_at,r.id
           LIMIT :limit OFFSET :offset""",
        {"course": course_id, "status": status, "limit": limit, "offset": offset},
    )
    return result(request, rows)


@router.patch(
    "/membership-requests/{request_user_id}", dependencies=Write,
    response_model=SuccessResponse[dict]
)
async def review_membership_request(
    course_id: Id,
    request_user_id: Id,
    body: MembershipReviewInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ForumService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True)
    changed = await service.repo.execute(
        """UPDATE forum_membership_requests SET status=:status,reason=:reason,
           reviewed_by=:reviewer,reviewed_at=UTC_TIMESTAMP(6)
           WHERE course_id=:course AND user_id=:member""",
        {
            "status": body.status,
            "reason": body.reason,
            "reviewer": int(user.id),
            "course": course_id,
            "member": request_user_id,
        },
    )
    if not changed:
        raise HTTPException(404)
    await service.audit(
        "forum.membership.review",
        "forum_membership_request",
        request_user_id,
        details={"course_id": course_id, "status": body.status},
    )
    await connection.commit()
    row = await service.repo.fetch_one(
        """SELECT id,course_id,user_id,status,reason,reviewed_by,reviewed_at,created_at,updated_at
           FROM forum_membership_requests WHERE course_id=:course AND user_id=:member""",
        {"course": course_id, "member": request_user_id},
    )
    return result(request, row)
