"""Question bank, blueprint, exam and attempt API."""

import random
from datetime import UTC
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.course.presentation.router import Id, Publish, Read, Write
from src.modules.quiz_exam.application.service import ExamService

router = APIRouter(prefix="/api/v1", tags=["Exams"], responses=ERROR_RESPONSES)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NameInput(Input):
    name: str = Field(min_length=1, max_length=255)


class OptionInput(Input):
    key: str = Field(min_length=1, max_length=16)
    text: str = Field(min_length=1, max_length=4000)
    is_correct: bool = False


class QuestionInput(Input):
    question_type: Literal["SINGLE", "MULTIPLE", "TRUE_FALSE"]
    prompt: str = Field(min_length=1, max_length=16000)
    explanation: str | None = Field(default=None, max_length=16000)
    points: float = Field(default=1, gt=0, le=999999.99)
    category_id: int | None = Field(default=None, gt=0)
    difficulty: Literal["EASY", "MEDIUM", "HARD"] = "MEDIUM"
    options: list[OptionInput] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def validate_options(self):
        correct = sum(o.is_correct for o in self.options)
        if (
            len({o.key for o in self.options}) != len(self.options)
            or not correct
            or (self.question_type != "MULTIPLE" and correct != 1)
            or (self.question_type == "TRUE_FALSE" and len(self.options) != 2)
        ):
            raise ValueError("Invalid options or correct answer count")
        return self


class ExamQuestion(Input):
    question_id: int = Field(gt=0)
    position: int = Field(gt=0)
    points: float = Field(default=1, gt=0, le=999999.99)


class Blueprint(Input):
    bank_id: int = Field(gt=0)
    category_id: int | None = Field(default=None, gt=0)
    difficulty: Literal["EASY", "MEDIUM", "HARD"] | None = None
    question_type: Literal["SINGLE", "MULTIPLE", "TRUE_FALSE"]
    question_count: int = Field(ge=1, le=1000)
    points_each: float = Field(gt=0, le=999999.99)


class ExamInput(Input):
    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=16000)
    opens_at: AwareDatetime
    due_at: AwareDatetime
    duration_seconds: int = Field(gt=0, le=86400)
    max_attempts: int = Field(default=1, ge=1, le=100)
    shuffle_questions: bool = False
    show_results: bool = False
    pass_score: float = Field(default=0, ge=0, le=999999.99)
    allow_resume: bool = True
    questions: list[ExamQuestion] = Field(default_factory=list, max_length=1000)
    blueprint: list[Blueprint] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_exam(self):
        total = sum(q.points for q in self.questions) + sum(
            b.points_each * b.question_count for b in self.blueprint
        )
        if (
            self.opens_at >= self.due_at
            or bool(self.questions) == bool(self.blueprint)
            or len({q.question_id for q in self.questions}) != len(self.questions)
            or len({q.position for q in self.questions}) != len(self.questions)
            or len({b.question_type for b in self.blueprint}) != len(self.blueprint)
            or total > 999999.99
            or self.pass_score > total
        ):
            raise ValueError("Invalid window, question selection or score")
        return self


class AnswerInput(Input):
    selected_option_ids: list[int] = Field(default_factory=list, max_length=20)
    expected_version: int = Field(ge=0)


def service(connection, user, request):
    return ExamService(connection, user, request.state.trace_id)


def result(request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


@router.post(
    "/courses/{course_id}/question-banks",
    dependencies=Write,
    status_code=201,
    response_model=SuccessResponse[dict],
)
async def create_bank(
    course_id: Id,
    body: NameInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    s = service(connection, user, request)
    await s.manager(course_id)
    id = await s.repo.insert(
        """INSERT INTO question_banks(course_id,name,created_by)
        VALUES (:course,:name,:user)""",
        {"course": course_id, "name": body.name, "user": int(user.id)},
    )
    await s.finish("bank.create", "question_bank", id)
    return result(request, {"id": str(id), "name": body.name})


@router.get(
    "/courses/{course_id}/question-banks",
    dependencies=Write,
    response_model=SuccessResponse[list[dict]],
)
async def list_banks(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    s = service(connection, user, request)
    await s.manager(course_id)
    return result(
        request,
        await s.repo.fetch_all(
            "SELECT * FROM question_banks WHERE course_id=:id ORDER BY id", {"id": course_id}
        ),
    )


@router.post(
    "/question-banks/{bank_id}/categories",
    dependencies=Write,
    status_code=201,
    response_model=SuccessResponse[dict],
)
async def create_category(
    bank_id: Id,
    body: NameInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    s = service(connection, user, request)
    await s.bank(bank_id)
    id = await s.repo.insert(
        "INSERT INTO question_categories(bank_id,name) VALUES (:bank,:name)",
        {"bank": bank_id, "name": body.name},
    )
    await s.finish("category.create", "question_category", id)
    return result(request, {"id": str(id), "name": body.name})


@router.get(
    "/question-banks/{bank_id}/categories",
    dependencies=Write,
    response_model=SuccessResponse[list[dict]],
)
async def list_categories(
    bank_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    s = service(connection, user, request)
    await s.bank(bank_id)
    return result(
        request,
        await s.repo.fetch_all(
            "SELECT * FROM question_categories WHERE bank_id=:id ORDER BY id", {"id": bank_id}
        ),
    )


@router.post(
    "/question-banks/{bank_id}/questions",
    dependencies=Write,
    status_code=201,
    response_model=SuccessResponse[dict],
)
async def create_question(
    bank_id: Id,
    body: QuestionInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    s = service(connection, user, request)
    await s.bank(bank_id)
    if body.category_id and not await s.repo.fetch_one(
        "SELECT id FROM question_categories WHERE id=:id AND bank_id=:bank",
        {"id": body.category_id, "bank": bank_id},
    ):
        raise HTTPException(422, "Category outside bank")
    id = await s.repo.insert(
        """INSERT INTO questions
        (bank_id,question_type,prompt,explanation,points,category_id,difficulty,status)
        VALUES (:bank,:question_type,:prompt,:explanation,:points,:category_id,
                :difficulty,'PUBLISHED')""",
        body.model_dump(exclude={"options"}) | {"bank": bank_id},
    )
    for option in body.options:
        await s.repo.insert(
            """INSERT INTO question_options
            (question_id,option_key,option_text,is_correct) VALUES (:id,:key,:text,:is_correct)""",
            option.model_dump() | {"id": id},
        )
    row = await s.question(id)
    await s.finish("question.create", "question", id)
    return result(request, row)


@router.get(
    "/question-banks/{bank_id}/questions",
    dependencies=Write,
    response_model=SuccessResponse[list[dict]],
)
async def list_questions(
    bank_id: Id,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
    difficulty: Literal["EASY", "MEDIUM", "HARD"] | None = None,
    category_id: int | None = None,
):
    s = service(connection, user, request)
    await s.bank(bank_id)
    rows = await s.repo.fetch_all(
        """SELECT id FROM questions WHERE bank_id=:bank
        AND (:difficulty IS NULL OR difficulty=:difficulty)
        AND (:category IS NULL OR category_id=:category) ORDER BY id""",
        {"bank": bank_id, "difficulty": difficulty, "category": category_id},
    )
    return result(request, [await s.question(row["id"]) for row in rows])


async def detail(s, id):
    row, _ = await s.exam(id)
    row["questions"] = await s.repo.fetch_all(
        "SELECT * FROM exam_questions WHERE exam_id=:id ORDER BY position", {"id": id}
    )
    row["blueprint"] = await s.repo.fetch_all(
        "SELECT * FROM exam_blueprints WHERE exam_id=:id", {"id": id}
    )
    return row


async def save_exam(s, course_id, body, id=None):
    await s.manager(course_id)
    for q in body.questions:
        row = await s.question(q.question_id)
        bank = await s.bank(row["bank_id"])
        if bank["course_id"] != course_id or row["status"] != "PUBLISHED":
            raise HTTPException(422, "Question outside course or unavailable")
    for b in body.blueprint:
        bank = await s.bank(b.bank_id)
        if bank["course_id"] != course_id:
            raise HTTPException(422, "Blueprint bank outside course")
        if b.category_id and not await s.repo.fetch_one(
            "SELECT id FROM question_categories WHERE id=:id AND bank_id=:bank",
            {"id": b.category_id, "bank": b.bank_id},
        ):
            raise HTTPException(422, "Blueprint category outside bank")
    values = body.model_dump(exclude={"questions", "blueprint"})
    for key in ("opens_at", "due_at"):
        values[key] = values[key].astimezone(UTC).replace(tzinfo=None)
    # Identifiers come exclusively from fixed schema fields, not client-supplied keys.
    if id:
        row, _ = await s.exam(id)
        if row["course_id"] != course_id:
            raise HTTPException(404)
        if row["status"] != "DRAFT":
            raise HTTPException(409, "Only draft exams can be edited")
        await s.repo.execute(
            "UPDATE exams SET " + ",".join(k + "=:" + k for k in values) + " WHERE id=:id",
            values | {"id": id},
        )
        await s.repo.execute("DELETE FROM exam_questions WHERE exam_id=:id", {"id": id})
        await s.repo.execute("DELETE FROM exam_blueprints WHERE exam_id=:id", {"id": id})
    else:
        id = await s.repo.insert(
            "INSERT INTO exams ("
            + ",".join(values)
            + ",course_id,created_by) VALUES ("
            + ",".join(":" + k for k in values)
            + ",:course,:user)",
            values | {"course": course_id, "user": int(s.user.id)},
        )
    for q in body.questions:
        await s.repo.insert(
            """INSERT INTO exam_questions(exam_id,question_id,position,points)
            VALUES (:exam,:question_id,:position,:points)""",
            q.model_dump() | {"exam": id},
        )
    for b in body.blueprint:
        await s.repo.insert(
            """INSERT INTO exam_blueprints
            (exam_id,bank_id,category_id,difficulty,question_type,question_count,points_each)
            VALUES (:exam,:bank_id,:category_id,:difficulty,:question_type,
                    :question_count,:points_each)""",
            b.model_dump() | {"exam": id},
        )
    row = await detail(s, id)
    await s.finish("exam.save", "exam", id)
    return row


@router.post(
    "/courses/{course_id}/exams",
    dependencies=Write,
    status_code=201,
    response_model=SuccessResponse[dict],
)
async def create_exam(
    course_id: Id,
    body: ExamInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    return result(request, await save_exam(service(connection, user, request), course_id, body))


@router.put(
    "/courses/{course_id}/exams/{exam_id}", dependencies=Write, response_model=SuccessResponse[dict]
)
async def update_exam(
    course_id: Id,
    exam_id: Id,
    body: ExamInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    return result(
        request, await save_exam(service(connection, user, request), course_id, body, exam_id)
    )


@router.get(
    "/courses/{course_id}/exams", dependencies=Read, response_model=SuccessResponse[list[dict]]
)
async def list_exams(
    course_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    s = service(connection, user, request)
    course = await s.authorize(course_id)
    manager = "ADMIN" in user.roles or (
        "INSTRUCTOR" in user.roles
        and (
            course["created_by"] == int(user.id)
            or await s.repo.fetch_one(
                "SELECT id FROM course_staff WHERE course_id=:id "
                "AND user_id=:user AND role='INSTRUCTOR'",
                {"id": course_id, "user": int(user.id)},
            )
        )
    )
    return result(
        request,
        await s.repo.fetch_all(
            """SELECT id,title,status,opens_at,due_at,
        duration_seconds FROM exams WHERE course_id=:id AND (:manager=1 OR status='PUBLISHED')
        ORDER BY id""",
            {"id": course_id, "manager": bool(manager)},
        ),
    )


@router.get("/exams/{exam_id}", dependencies=Write, response_model=SuccessResponse[dict])
async def get_exam(
    exam_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    return result(request, await detail(service(connection, user, request), exam_id))


@router.delete("/exams/{exam_id}", dependencies=Write, response_model=SuccessResponse[dict])
async def delete_exam(
    exam_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    s = service(connection, user, request)
    row, _ = await s.exam(exam_id)
    if row["status"] != "DRAFT":
        raise HTTPException(409, "Only draft exams can be deleted")
    await s.repo.execute("DELETE FROM exams WHERE id=:id", {"id": exam_id})
    await s.finish("exam.delete", "exam", exam_id)
    return result(request, {"id": str(exam_id)})


@router.post("/exams/{exam_id}/publish", dependencies=Publish, response_model=SuccessResponse[dict])
async def publish_exam(
    exam_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    s = service(connection, user, request)
    row, _ = await s.exam(exam_id)
    if row["status"] != "DRAFT" or row["due_at"] <= await s.now():
        raise HTTPException(409, "Exam cannot be published")
    blueprint = await s.repo.fetch_all(
        "SELECT * FROM exam_blueprints WHERE exam_id=:id", {"id": exam_id}
    )
    position = 0
    for b in blueprint:
        candidates = await s.repo.fetch_all(
            """SELECT id FROM questions WHERE bank_id=:bank_id
            AND status='PUBLISHED' AND question_type=:question_type
            AND (:category_id IS NULL OR category_id=:category_id)
            AND (:difficulty IS NULL OR difficulty=:difficulty) ORDER BY id FOR UPDATE""",
            b,
        )
        if len(candidates) < b["question_count"]:
            raise HTTPException(409, "Insufficient questions for blueprint")
        for q in random.SystemRandom().sample(candidates, b["question_count"]):
            position += 1
            await s.repo.insert(
                """INSERT INTO exam_questions(exam_id,question_id,position,points)
                VALUES (:exam,:q,:position,:points)""",
                {"exam": exam_id, "q": q["id"], "position": position, "points": b["points_each"]},
            )
    questions = await s.repo.fetch_all(
        "SELECT * FROM exam_questions WHERE exam_id=:id", {"id": exam_id}
    )
    if not questions or row["pass_score"] > sum(q["points"] for q in questions):
        raise HTTPException(409, "Invalid exam score or empty exam")
    for q in questions:
        question = await s.question(q["question_id"])
        bank = await s.bank(question["bank_id"])
        correct = sum(o["is_correct"] for o in question["options"])
        if (
            bank["course_id"] != row["course_id"]
            or question["status"] != "PUBLISHED"
            or len(question["options"]) < 2
            or correct < 1
            or (question["question_type"] != "MULTIPLE" and correct != 1)
        ):
            raise HTTPException(409, "Invalid question")
    await s.repo.execute("UPDATE exams SET status='PUBLISHED' WHERE id=:id", {"id": exam_id})
    await s.finish("exam.publish", "exam", exam_id)
    return result(request, {"id": str(exam_id), "status": "PUBLISHED"})


@router.get("/exams/{exam_id}/eligibility", dependencies=Read, response_model=SuccessResponse[dict])
async def eligibility(
    exam_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    _, _, _, data = await service(connection, user, request).eligibility(exam_id)
    await connection.commit()
    return result(request, data)


@router.post(
    "/exams/{exam_id}/attempts",
    dependencies=Read,
    status_code=201,
    response_model=SuccessResponse[dict],
)
async def start_attempt(
    exam_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    return result(request, await service(connection, user, request).start(exam_id))


@router.get("/attempts/{attempt_id}", dependencies=Read, response_model=SuccessResponse[dict])
async def resume_attempt(
    attempt_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    return result(request, await service(connection, user, request).view(attempt_id))


@router.put(
    "/attempts/{attempt_id}/answers/{question_id}",
    dependencies=Read,
    response_model=SuccessResponse[dict],
)
async def autosave(
    attempt_id: Id,
    question_id: Id,
    body: AnswerInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    return result(
        request, await service(connection, user, request).save(attempt_id, question_id, body)
    )


@router.post(
    "/attempts/{attempt_id}/submit", dependencies=Read, response_model=SuccessResponse[dict]
)
async def submit_attempt(
    attempt_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    return result(request, await service(connection, user, request).submit(attempt_id))
