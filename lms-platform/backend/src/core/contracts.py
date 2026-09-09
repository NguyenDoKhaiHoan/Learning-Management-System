"""Version 1 API envelopes; exported as JSON Schema for frontend consumers."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    location: list[str | int] = Field(default_factory=list)
    type: str
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    trace_id: str


class SuccessResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "Success"
    data: T
    trace_id: str


class CurrentUser(BaseModel):
    model_config = ConfigDict(frozen=True)
    # BIGINT is represented as a string in JSON to avoid JS precision loss.
    id: str
    email: str
    username: str
    roles: tuple[str, ...]


ERROR_RESPONSES = {
    status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 422, 500, 503)
}
