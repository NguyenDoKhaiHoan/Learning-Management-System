"""Basic course-scoped discussion forum API."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.course.presentation.router import Id, Read
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
    created_at: datetime
    updated_at: datetime


class ThreadDetail(ThreadOutput):
    messages: list[MessageOutput] = Field(default_factory=list)


class Page(BaseModel):
    items: list[ThreadOutput]
    total: int
    limit: int
    offset: int


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


@router.post("/threads", status_code=201, response_model=SuccessResponse[ThreadOutput])
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


@router.post(
    "/threads/{thread_id}/messages",
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
    thread = await service.get_thread(course_id, thread_id)
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
