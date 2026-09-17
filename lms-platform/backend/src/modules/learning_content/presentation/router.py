"""Module/lesson metadata CRUD and atomic full-sibling ordering."""

from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.course.presentation.router import Id, Read, Write
from src.modules.learning_content.application.service import ContentService
from src.modules.learning_content.domain.enums import LessonType
from src.modules.learning_content.infrastructure.repository import ContentRepository

router = APIRouter(
    prefix="/api/v1/courses/{course_id}/modules", tags=["Content"], responses=ERROR_RESPONSES
)


class ModuleInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=255)


class LessonInput(ModuleInput):
    lesson_type: LessonType
    is_preview: bool = False
    content: str | None = Field(default=None, max_length=16000)


class LessonOutput(LessonInput):
    model_config = ConfigDict(coerce_numbers_to_str=True, extra="ignore")
    id: str
    position: int


class ModuleOutput(ModuleInput):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    id: str
    position: int
    lessons: list[LessonOutput] = Field(default_factory=list)


class OrderInput(BaseModel):
    ids: list[Annotated[int, Field(gt=0, le=18446744073709551615)]] = Field(max_length=10000)


def result(request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.get("", dependencies=Read, response_model=SuccessResponse[list[ModuleOutput]])
async def curriculum(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id)
    modules = await service.repo.fetch_all(
        """SELECT id, title, position FROM modules WHERE course_id=:id AND deleted_at IS NULL
           ORDER BY position""",
        {"id": course_id},
    )
    lessons = await service.repo.fetch_all(
        """SELECT l.id, l.module_id, l.title, l.position, l.lesson_type, l.is_preview, l.content
           FROM lessons l JOIN modules m ON m.id=l.module_id WHERE m.course_id=:id
           AND m.deleted_at IS NULL AND l.deleted_at IS NULL ORDER BY l.position""",
        {"id": course_id},
    )
    for module in modules:
        module["lessons"] = [row for row in lessons if row["module_id"] == module["id"]]
    return result(request, modules)


@router.post(
    "", dependencies=Write, status_code=201, response_model=SuccessResponse[dict[str, str]]
)
async def create_module(
    course_id: Id,
    body: ModuleInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    row_id = await ContentRepository(connection).create_module(
        course_id=course_id,
        title=body.title,
        position=await service.next_position("module", course_id),
    )
    await service.finish("module.create", "module", row_id)
    return result(request, {"id": str(row_id)})


@router.put("/order", dependencies=Write, response_model=SuccessResponse[dict[str, bool]])
async def order_modules(
    course_id: Id,
    body: OrderInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.reorder("module", course_id, body.ids)
    return result(request, {"ordered": True})


@router.put("/{module_id}", dependencies=Write, response_model=SuccessResponse[dict[str, str]])
async def update_module(
    course_id: Id,
    module_id: Id,
    body: ModuleInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.module(course_id, module_id)
    await service.repo.execute(
        "UPDATE modules SET title=:title WHERE id=:id", {"title": body.title, "id": module_id}
    )
    await service.finish("module.update", "module", module_id)
    return result(request, {"id": str(module_id)})


@router.delete("/{module_id}", dependencies=Write, response_model=SuccessResponse[dict[str, str]])
async def delete_module(
    course_id: Id,
    module_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.module(course_id, module_id)
    await service.repo.execute(
        "UPDATE modules SET deleted_at=UTC_TIMESTAMP(6) WHERE id=:id", {"id": module_id}
    )
    await service.finish("module.delete", "module", module_id)
    return result(request, {"id": str(module_id)})


@router.post(
    "/{module_id}/lessons",
    dependencies=Write,
    status_code=201,
    response_model=SuccessResponse[dict[str, str]],
)
async def create_lesson(
    course_id: Id,
    module_id: Id,
    body: LessonInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.module(course_id, module_id)
    row_id = await ContentRepository(connection).create_lesson(
        module_id=module_id,
        position=await service.next_position("lesson", module_id),
        **body.model_dump(),
    )
    await service.finish("lesson.create", "lesson", row_id)
    return result(request, {"id": str(row_id)})


@router.put(
    "/{module_id}/lessons/order",
    dependencies=Write,
    response_model=SuccessResponse[dict[str, bool]],
)
async def order_lessons(
    course_id: Id,
    module_id: Id,
    body: OrderInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.module(course_id, module_id)
    await service.reorder("lesson", module_id, body.ids)
    return result(request, {"ordered": True})


@router.get(
    "/{module_id}/lessons/{lesson_id}",
    dependencies=Read,
    response_model=SuccessResponse[LessonOutput],
)
async def get_lesson(
    course_id: Id,
    module_id: Id,
    lesson_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id)
    return result(request, await service.lesson(course_id, module_id, lesson_id))


@router.put(
    "/{module_id}/lessons/{lesson_id}",
    dependencies=Write,
    response_model=SuccessResponse[dict[str, str]],
)
async def update_lesson(
    course_id: Id,
    module_id: Id,
    lesson_id: Id,
    body: LessonInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.lesson(course_id, module_id, lesson_id)
    await service.repo.execute(
        """UPDATE lessons SET title=:title, lesson_type=:lesson_type,
           is_preview=:is_preview, content=:content WHERE id=:id""",
        {**body.model_dump(), "id": lesson_id},
    )
    await service.finish("lesson.update", "lesson", lesson_id)
    return result(request, {"id": str(lesson_id)})


@router.delete(
    "/{module_id}/lessons/{lesson_id}",
    dependencies=Write,
    response_model=SuccessResponse[dict[str, str]],
)
async def delete_lesson(
    course_id: Id,
    module_id: Id,
    lesson_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    service = ContentService(connection, user, request.state.trace_id)
    await service.authorize(course_id, write=True, draft=True)
    await service.lesson(course_id, module_id, lesson_id)
    await service.repo.execute(
        "UPDATE lessons SET deleted_at=UTC_TIMESTAMP(6) WHERE id=:id", {"id": lesson_id}
    )
    await service.finish("lesson.delete", "lesson", lesson_id)
    return result(request, {"id": str(lesson_id)})
