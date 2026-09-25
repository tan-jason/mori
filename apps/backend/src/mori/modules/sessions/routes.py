"""Authenticated session planning routes."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response

from mori.api.auth import session_token, verify_csrf
from mori.modules.identity.application import IdentityService
from mori.modules.sessions.application import SessionService
from mori.modules.sessions.errors import InvalidIdempotencyKey
from mori.modules.sessions.schemas import CreateSessionRequest, SessionResponse

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(
    request: Request,
    response: Response,
    body: CreateSessionRequest,
    idempotency_key: str | None = Header(default=None),
) -> SessionResponse:
    token = session_token(request)
    verify_csrf(request, token)
    if idempotency_key is None:
        raise InvalidIdempotencyKey
    identity = cast(IdentityService, request.app.state.identity_service)
    learner = await identity.current_learner(session_token=token)
    service = cast(SessionService, request.app.state.session_service)
    result, created = await service.create(
        user_id=learner.user_id,
        language_profile_id=body.language_profile_id,
        idempotency_key=idempotency_key,
    )
    response.status_code = 201 if created else 200
    response.headers["Location"] = f"/api/v1/sessions/{result.id}"
    return SessionResponse.from_view(result)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(request: Request, session_id: UUID) -> SessionResponse:
    token = session_token(request)
    identity = cast(IdentityService, request.app.state.identity_service)
    learner = await identity.current_learner(session_token=token)
    service = cast(SessionService, request.app.state.session_service)
    return SessionResponse.from_view(
        await service.get(user_id=learner.user_id, session_id=session_id)
    )
