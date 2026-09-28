"""Current learner HTTP read model."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request, Response

from mori.api.auth import session_token as _session_token
from mori.modules.identity.application import IdentityService
from mori.modules.users.application import UserService
from mori.modules.users.schemas import MeResponse

router = APIRouter()


def _user_service(request: Request) -> UserService:
    return cast(UserService, request.app.state.user_service)


def _identity(request: Request) -> IdentityService:
    return cast(IdentityService, request.app.state.identity_service)


@router.get("/api/v1/me", response_model=MeResponse)
async def get_me(request: Request, response: Response) -> MeResponse:
    session_token = _session_token(request)
    service = _user_service(request)
    learner = await service.current_learner(session_token=session_token)
    response.headers["ETag"] = f'"{learner.version}"'
    response.headers["Cache-Control"] = "no-store"
    return MeResponse.from_domain(
        learner,
        csrf_token=_identity(request).csrf_token(session_token),
    )
