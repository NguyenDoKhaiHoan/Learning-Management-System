"""Week 1 protected endpoint; login/refresh endpoints are week 2 scope."""

from fastapi import APIRouter, Request

from src.core.contracts import ERROR_RESPONSES, CurrentUser, SuccessResponse
from src.core.security.dependencies import CurrentUserDependency

router = APIRouter(prefix="/api/v1/auth", tags=["Identity"], responses=ERROR_RESPONSES)


@router.get("/me", response_model=SuccessResponse[CurrentUser])
async def me(request: Request, user: CurrentUserDependency) -> SuccessResponse[CurrentUser]:
    return SuccessResponse(data=user, trace_id=request.state.trace_id)
