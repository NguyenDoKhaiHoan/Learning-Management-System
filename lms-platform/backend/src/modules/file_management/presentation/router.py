"""Private lesson resources: link metadata and streamed file upload/download."""

import hashlib
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from src.config.config import Settings
from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.course.presentation.router import Id, Read, Write
from src.modules.file_management.domain.policy import (
    ALLOWED_MIME_EXTENSIONS,
    normalized_mime,
    safe_display_name,
    validate_file_content,
)
from src.modules.learning_content.application.service import ContentService
from src.modules.learning_content.domain.enums import ResourceType
from src.modules.learning_content.infrastructure.repository import ContentRepository

router = APIRouter(
    prefix=(
        "/api/v1/courses/{course_id}/modules/{module_id}/lessons/{lesson_id}/resources"
    ),
    tags=["Lesson resources"],
    responses=ERROR_RESPONSES,
)


class LinkInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    url: HttpUrl


class ResourceOutput(BaseModel):
    model_config = ConfigDict(
        coerce_numbers_to_str=True,
        extra="ignore",
    )

    id: str
    lesson_id: str
    title: str
    resource_type: ResourceType

    mime_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    uploaded_by: str | None = None

    url: str | None = None


def result(request: Request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


async def context(course_id, module_id, lesson_id, request, connection, user, *, write=False):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=write, draft=write)
    await service.lesson(course_id, module_id, lesson_id)
    return service


@router.get("", dependencies=Read, response_model=SuccessResponse[list[ResourceOutput]])
async def list_resources(
    course_id: Id,
    module_id: Id,
    lesson_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    await context(course_id, module_id, lesson_id, request, connection, user)
    rows = await ContentRepository(connection).list_resources(lesson_id)
    for row in rows:
        location = row.pop(
        "location",
        None,
    )

        row["url"] = (
        location
        if row["resource_type"] == ResourceType.LINK
        else None
    )
    return result(request, rows)


@router.post(
    "", dependencies=Write, status_code=201, response_model=SuccessResponse[ResourceOutput]
)
async def create_link(
    course_id: Id,
    module_id: Id,
    lesson_id: Id,
    body: LinkInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = await context(
        course_id, module_id, lesson_id, request, connection, user, write=True
    )
    url = str(body.url)
    if urlparse(url).scheme not in {"http", "https"}:
        raise HTTPException(422, "Only HTTP(S) links are supported")
    repo = ContentRepository(connection)
    resource_id = await repo.add_resource(
        lesson_id=lesson_id,
        title=body.title,
        resource_type=ResourceType.LINK,
        location=url,
        uploaded_by=int(user.id),
    )
    await service.finish("lesson_resource.create", "lesson_resource", resource_id)
    return result(
        request,
        {
            "id": resource_id,
            "lesson_id": lesson_id,
            "title": body.title,
            "resource_type": ResourceType.LINK,
            "uploaded_by": int(user.id),
            "url": url,
        },
)


@router.post(
    "/file", dependencies=Write, status_code=201, response_model=SuccessResponse[ResourceOutput]
)
async def upload_file(
    course_id: Id,
    module_id: Id,
    lesson_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    file_name: Annotated[str, Header(alias="X-File-Name", min_length=1, max_length=255)],
):
    service = await context(
        course_id, module_id, lesson_id, request, connection, user, write=True
    )
    settings: Settings = request.app.state.settings
    content_length = request.headers.get("content-length")
    if content_length and (
        not content_length.isdigit() or int(content_length) > settings.max_upload_bytes
    ):
        raise HTTPException(413, "File exceeds configured size limit")
    mime_type = normalized_mime(request.headers.get("content-type"))
    display_name = safe_display_name(file_name)
    storage_root = settings.private_storage_root.resolve()
    directory = storage_root / "lessons" / str(lesson_id)
    directory.mkdir(parents=True, exist_ok=True)
    object_name = uuid4().hex + ALLOWED_MIME_EXTENSIONS[mime_type]
    relative_key = Path("lessons") / str(lesson_id) / object_name
    final_path = storage_root / relative_key
    temporary_path = final_path.with_suffix(final_path.suffix + ".upload")
    size = 0
    digest = hashlib.sha256()
    try:
        with temporary_path.open("xb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(413, "File exceeds configured size limit")
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise HTTPException(422, "File must not be empty")
        validate_file_content(temporary_path, mime_type)
        temporary_path.replace(final_path)
        repo = ContentRepository(connection)
        resource_id = await repo.add_resource(
            lesson_id=lesson_id,
            title=display_name,
            resource_type=ResourceType.FILE,
            location=relative_key.as_posix(),
            mime_type=mime_type,
            size_bytes=size,
            sha256=digest.hexdigest(),
            uploaded_by=int(user.id),
        )
        await service.finish("lesson_resource.upload", "lesson_resource", resource_id)
        return result(
            request,
            {
                "id": resource_id,
                "lesson_id": lesson_id,
                "title": display_name,
                "resource_type": ResourceType.FILE,
                "mime_type": mime_type,
                "size_bytes": size,
                "sha256": digest.hexdigest(),
                "uploaded_by": int(user.id),
            },
        )
    except Exception:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise


@router.get("/{resource_id}/content", dependencies=Read)
async def download_file(
    course_id: Id,
    module_id: Id,
    lesson_id: Id,
    resource_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    await context(course_id, module_id, lesson_id, request, connection, user)
    row = await ContentRepository(connection).get_resource(resource_id)
    if row is None or row["lesson_id"] != lesson_id:
        raise HTTPException(404)
    if row["resource_type"] != ResourceType.FILE:
        raise HTTPException(409, "Resource is not a stored file")
    root = request.app.state.settings.private_storage_root.resolve()
    path = (root / row["location"]).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type=row["mime_type"], filename=row["title"])


@router.delete(
    "/{resource_id}", dependencies=Write, response_model=SuccessResponse[dict[str, str]]
)
async def delete_resource(
    course_id: Id,
    module_id: Id,
    lesson_id: Id,
    resource_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = await context(
        course_id, module_id, lesson_id, request, connection, user, write=True
    )
    repo = ContentRepository(connection)
    row = await repo.get_resource(resource_id, for_update=True)
    if row is None or row["lesson_id"] != lesson_id:
        raise HTTPException(404)
    await repo.execute(
        "UPDATE lesson_resources SET deleted_at=UTC_TIMESTAMP(6) WHERE id=:id",
        {"id": resource_id},
    )
    await service.finish("lesson_resource.delete", "lesson_resource", resource_id)
    return result(request, {"id": str(resource_id)})
