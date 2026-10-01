"""Question bank and exam MVP APIs for the week 4 assessment flow."""
# ruff: noqa: E501
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from src.core.contracts import ERROR_RESPONSES, SuccessResponse
from src.core.database.database import ConnectionDependency
from src.core.security.dependencies import CurrentUserDependency
from src.modules.course.application.service import CourseService

router = APIRouter(prefix="/api/v1", tags=["Exams"], responses=ERROR_RESPONSES)
Id = Annotated[int, Path(gt=0, le=18446744073709551615)]


class OptionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    key: str = Field(min_length=1, max_length=16)
    text: str = Field(min_length=1, max_length=4000)
    is_correct: bool = False


class QuestionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    question_type: str = Field(pattern="^(SINGLE|MULTIPLE|TRUE_FALSE)$")
    prompt: str = Field(min_length=1, max_length=16000)
    explanation: str | None = Field(default=None, max_length=16000)
    points: float = Field(default=1, gt=0, le=999999.99)
    options: list[OptionInput] = Field(default_factory=list, max_length=20)


class BankInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=16000)


class ExamQuestionInput(BaseModel):
    question_id: int = Field(gt=0)
    position: int = Field(gt=0)
    points: float = Field(default=1, gt=0, le=999999.99)


class ExamInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=16000)
    opens_at: datetime
    due_at: datetime
    duration_seconds: int = Field(gt=0, le=86400)
    max_attempts: int = Field(default=1, ge=1, le=100)
    shuffle_questions: bool = False
    show_results: bool = False
    pass_score: float = Field(default=0, ge=0, le=999999.99)
    questions: list[ExamQuestionInput] = Field(min_length=1, max_length=1000)


class AnswerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_option_ids: list[int] | None = None
    answer_text: str | None = Field(default=None, max_length=16000)


def result(request: Request, data):
    return SuccessResponse(data=data, trace_id=request.state.trace_id)


async def manager(connection, user, course_id: int):
    if not {"ADMIN", "INSTRUCTOR"}.intersection(user.roles):
        raise HTTPException(403)
    return await CourseService(connection, user, "week4").authorize(
        course_id, write=True, draft=True
    )


async def exam_for(connection, exam_id: int, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    row = await connection.execute(
        text(f"SELECT * FROM exams WHERE id=:id{suffix}"), {"id": exam_id}
    )
    return row.mappings().first()


@router.post(
    "/courses/{course_id}/question-banks", status_code=201, response_model=SuccessResponse[dict]
)
async def create_bank(
    course_id: Id,
    body: BankInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    await manager(connection, user, course_id)
    row = await connection.execute(
        text(
            "INSERT INTO question_banks(course_id,name,description,created_by) VALUES (:course,:name,:description,:user)"
        ),
        {
            "course": course_id,
            "name": body.name,
            "description": body.description,
            "user": int(user.id),
        },
    )
    bank_id = row.lastrowid
    await connection.commit()
    return result(
        request,
        {"id": str(bank_id), "course_id": str(course_id), **body.model_dump(), "status": "DRAFT"},
    )


@router.post(
    "/question-banks/{bank_id}/questions", status_code=201, response_model=SuccessResponse[dict]
)
async def create_question(
    bank_id: Id,
    body: QuestionInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    bank = (
        (
            await connection.execute(
                text("SELECT * FROM question_banks WHERE id=:id"), {"id": bank_id}
            )
        )
        .mappings()
        .first()
    )
    if not bank:
        raise HTTPException(404)
    await manager(connection, user, int(bank["course_id"]))
    row = await connection.execute(
        text(
            "INSERT INTO questions(bank_id,question_type,prompt,explanation,points) VALUES (:bank,:type,:prompt,:explanation,:points)"
        ),
        {
            "bank": bank_id,
            "type": body.question_type,
            "prompt": body.prompt,
            "explanation": body.explanation,
            "points": body.points,
        },
    )
    question_id = row.lastrowid
    for option in body.options:
        await connection.execute(
            text(
                "INSERT INTO question_options(question_id,option_key,option_text,is_correct) VALUES (:question,:key,:text,:correct)"
            ),
            {
                "question": question_id,
                "key": option.key,
                "text": option.text,
                "correct": option.is_correct,
            },
        )
    await connection.commit()
    return result(request, {"id": str(question_id), "bank_id": str(bank_id), **body.model_dump()})


@router.post("/courses/{course_id}/exams", status_code=201, response_model=SuccessResponse[dict])
async def create_exam(
    course_id: Id,
    body: ExamInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    await manager(connection, user, course_id)
    if body.opens_at >= body.due_at:
        raise HTTPException(422, "opens_at must be before due_at")
    row = await connection.execute(
        text("""INSERT INTO exams(course_id,title,instructions,opens_at,due_at,duration_seconds,max_attempts,shuffle_questions,show_results,pass_score,created_by)
        VALUES (:course,:title,:instructions,:opens,:due,:duration,:attempts,:shuffle,:results,:pass,:user)"""),
        {
            "course": course_id,
            "title": body.title,
            "instructions": body.instructions,
            "opens": body.opens_at.astimezone(UTC).replace(tzinfo=None),
            "due": body.due_at.astimezone(UTC).replace(tzinfo=None),
            "duration": body.duration_seconds,
            "attempts": body.max_attempts,
            "shuffle": body.shuffle_questions,
            "results": body.show_results,
            "pass": body.pass_score,
            "user": int(user.id),
        },
    )
    exam_id = row.lastrowid
    for question in body.questions:
        await connection.execute(
            text(
                "INSERT INTO exam_questions(exam_id,question_id,position,points) VALUES (:exam,:question,:position,:points)"
            ),
            {
                "exam": exam_id,
                "question": question.question_id,
                "position": question.position,
                "points": question.points,
            },
        )
    await connection.commit()
    return result(
        request,
        {
            "id": str(exam_id),
            "course_id": str(course_id),
            "status": "DRAFT",
            **body.model_dump(exclude={"questions"}),
            "questions": body.questions,
        },
    )


@router.post("/exams/{exam_id}/publish", response_model=SuccessResponse[dict])
async def publish_exam(
    exam_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    exam = await exam_for(connection, exam_id)
    if not exam:
        raise HTTPException(404)
    await manager(connection, user, int(exam["course_id"]))
    await connection.execute(
        text("UPDATE exams SET status='PUBLISHED' WHERE id=:id AND status='DRAFT'"), {"id": exam_id}
    )
    await connection.commit()
    return result(request, {"id": str(exam_id), "status": "PUBLISHED"})


@router.get("/exams/{exam_id}/eligibility", response_model=SuccessResponse[dict])
async def eligibility(
    exam_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    row = (
        (
            await connection.execute(
                text("""SELECT x.id,x.status,x.opens_at,x.due_at,x.max_attempts,
        (SELECT COUNT(*) FROM exam_attempts a WHERE a.exam_id=x.id AND a.enrollment_id=e.id) attempts
        FROM exams x JOIN enrollments e ON e.course_id=x.course_id AND e.student_id=:user AND e.status='ACTIVE'
        WHERE x.id=:exam AND x.status='PUBLISHED'"""),
                {"exam": exam_id, "user": int(user.id)},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(403)
    now = datetime.now(UTC).replace(tzinfo=None)
    allowed = row["opens_at"] <= now <= row["due_at"] and row["attempts"] < row["max_attempts"]
    return result(
        request,
        {
            "exam_id": str(exam_id),
            "eligible": allowed,
            "attempts_used": row["attempts"],
            "max_attempts": row["max_attempts"],
        },
    )


@router.post("/exams/{exam_id}/attempts", status_code=201, response_model=SuccessResponse[dict])
async def start_attempt(
    exam_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    row = (
        (
            await connection.execute(
                text("""SELECT x.*,e.id enrollment_id,(SELECT COALESCE(MAX(attempt_no),0)+1 FROM exam_attempts a WHERE a.exam_id=x.id AND a.enrollment_id=e.id) attempt_no
        FROM exams x JOIN enrollments e ON e.course_id=x.course_id AND e.student_id=:user AND e.status='ACTIVE'
        WHERE x.id=:exam AND x.status='PUBLISHED' FOR UPDATE"""),
                {"exam": exam_id, "user": int(user.id)},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(403)
    now = datetime.now(UTC).replace(tzinfo=None)
    if now < row["opens_at"] or now > row["due_at"] or row["attempt_no"] > row["max_attempts"]:
        raise HTTPException(409, "Exam is not available")
    expires = min(now + timedelta(seconds=row["duration_seconds"]), row["due_at"])
    attempt = await connection.execute(
        text("""INSERT INTO exam_attempts(exam_id,enrollment_id,attempt_no,status,started_at,expires_at,max_score)
        SELECT :exam,:enrollment,:number,'IN_PROGRESS',:started,:expires,COALESCE(SUM(points),0) FROM exam_questions WHERE exam_id=:exam"""),
        {
            "exam": exam_id,
            "enrollment": row["enrollment_id"],
            "number": row["attempt_no"],
            "started": now,
            "expires": expires,
        },
    )
    await connection.commit()
    return result(
        request,
        {
            "id": str(attempt.lastrowid),
            "exam_id": str(exam_id),
            "attempt_no": row["attempt_no"],
            "status": "IN_PROGRESS",
            "started_at": now,
            "expires_at": expires,
        },
    )


@router.put("/attempts/{attempt_id}/answers/{question_id}", response_model=SuccessResponse[dict])
async def autosave(
    attempt_id: Id,
    question_id: Id,
    body: AnswerInput,
    request: Request,
    connection: ConnectionDependency,
    user: CurrentUserDependency,
):
    attempt = (
        (
            await connection.execute(
                text("""SELECT a.* FROM exam_attempts a JOIN enrollments e ON e.id=a.enrollment_id
        WHERE a.id=:attempt AND e.student_id=:user FOR UPDATE"""),
                {"attempt": attempt_id, "user": int(user.id)},
            )
        )
        .mappings()
        .first()
    )
    if not attempt:
        raise HTTPException(404)
    now = datetime.now(UTC).replace(tzinfo=None)
    if attempt["status"] != "IN_PROGRESS" or now >= attempt["expires_at"]:
        raise HTTPException(409, "Attempt has expired or was submitted")
    await connection.execute(
        text("""INSERT INTO exam_answers(attempt_id,question_id,selected_option_ids,answer_text,answered_at)
        VALUES (:attempt,:question,:options,:answer,:now)
        ON DUPLICATE KEY UPDATE selected_option_ids=:options,answer_text=:answer,answered_at=:now"""),
        {
            "attempt": attempt_id,
            "question": question_id,
            "options": body.selected_option_ids,
            "answer": body.answer_text,
            "now": now,
        },
    )
    await connection.execute(
        text("UPDATE exam_attempts SET server_version=server_version+1 WHERE id=:id"),
        {"id": attempt_id},
    )
    await connection.commit()
    return result(
        request, {"attempt_id": str(attempt_id), "question_id": str(question_id), "saved_at": now}
    )


@router.post("/attempts/{attempt_id}/submit", response_model=SuccessResponse[dict])
async def submit_attempt(
    attempt_id: Id, request: Request, connection: ConnectionDependency, user: CurrentUserDependency
):
    attempt = (
        (
            await connection.execute(
                text("""SELECT a.* FROM exam_attempts a JOIN enrollments e ON e.id=a.enrollment_id
        WHERE a.id=:attempt AND e.student_id=:user FOR UPDATE"""),
                {"attempt": attempt_id, "user": int(user.id)},
            )
        )
        .mappings()
        .first()
    )
    if not attempt:
        raise HTTPException(404)
    if attempt["status"] != "IN_PROGRESS":
        raise HTTPException(409, "Attempt already submitted")
    now = datetime.now(UTC).replace(tzinfo=None)
    status = "AUTO_SUBMITTED" if now >= attempt["expires_at"] else "SUBMITTED"
    await connection.execute(
        text("UPDATE exam_attempts SET status=:status,submitted_at=:now WHERE id=:id"),
        {"status": status, "now": now, "id": attempt_id},
    )
    await connection.commit()
    return result(request, {"id": str(attempt_id), "status": status, "submitted_at": now})
