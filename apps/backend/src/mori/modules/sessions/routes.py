"""Authenticated session planning routes."""

from __future__ import annotations

from contextlib import suppress
from hashlib import sha256
from hmac import new as hmac_new
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import PlainTextResponse

from mori.api.auth import session_token, verify_csrf
from mori.api.contracts import mutation_headers
from mori.config import Environment, Settings
from mori.modules.sessions.application import SessionService
from mori.modules.sessions.errors import (
    InvalidIdempotencyKey,
    InvalidSessionSetup,
    VoiceNotConfigured,
    VoiceProviderUnavailable,
)
from mori.modules.sessions.realtime_provider import (
    AmbiguousProviderFailure,
    DefinitiveProviderFailure,
    OpenAIRealtimeProvider,
)
from mori.modules.sessions.schemas import (
    CreateSessionRequest,
    SessionResponse,
    VoiceAvailabilityResponse,
)
from mori.modules.sessions.supervisor import RealtimeSupervisor
from mori.modules.user.application import UserService

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, openapi_extra=mutation_headers("Idempotency-Key"))
async def create_session(
    request: Request,
    response: Response,
    body: CreateSessionRequest,
    idempotency_key: str | None = Header(default=None, include_in_schema=False),
) -> SessionResponse:
    token = session_token(request)
    verify_csrf(request, token)
    if idempotency_key is None:
        raise InvalidIdempotencyKey
    user_service = cast(UserService, request.app.state.user_service)
    learner = await user_service.current_learner(session_token=token)
    service = cast(SessionService, request.app.state.session_service)
    result, created = await service.create(
        user_id=learner.user_id,
        language_profile_id=body.language_profile_id,
        idempotency_key=idempotency_key,
        topic=body.topic,
        requested_words=body.requested_words,
    )
    response.status_code = 201 if created else 200
    response.headers["Location"] = f"/api/v1/sessions/{result.id}"
    return SessionResponse.from_view(result)


@router.get("/availability", response_model=VoiceAvailabilityResponse)
async def voice_availability(request: Request) -> VoiceAvailabilityResponse:
    token = session_token(request)
    await cast(UserService, request.app.state.user_service).current_learner(session_token=token)
    settings = cast(Settings, request.app.state.settings)
    supervisor = cast(RealtimeSupervisor | None, request.app.state.realtime_supervisor)
    return VoiceAvailabilityResponse(
        available=supervisor is not None and supervisor.healthy,
        maxCallSeconds=1200 if settings.environment == Environment.PRODUCTION else 120,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(request: Request, session_id: UUID) -> SessionResponse:
    token = session_token(request)
    user_service = cast(UserService, request.app.state.user_service)
    learner = await user_service.current_learner(session_token=token)
    service = cast(SessionService, request.app.state.session_service)
    return SessionResponse.from_view(
        await service.get(user_id=learner.user_id, session_id=session_id)
    )


@router.post("/{session_id}/webrtc", response_class=PlainTextResponse)
async def exchange_webrtc(request: Request, session_id: UUID) -> PlainTextResponse:
    token = session_token(request)
    verify_csrf(request, token)
    settings = cast(Settings, request.app.state.settings)
    supervisor = cast(RealtimeSupervisor | None, request.app.state.realtime_supervisor)
    provider = cast(OpenAIRealtimeProvider | None, request.app.state.realtime_provider)
    secret = settings.openai_safety_id_secret
    if supervisor is None or provider is None or secret is None or not supervisor.healthy:
        raise VoiceNotConfigured
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/sdp":
        raise InvalidSessionSetup
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 65536:
            raise InvalidSessionSetup
        chunks.append(chunk)
    try:
        offer = b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidSessionSetup from error
    if not offer.startswith("v=0"):
        raise InvalidSessionSetup
    learner = await cast(UserService, request.app.state.user_service).current_learner(
        session_token=token
    )
    service = cast(SessionService, request.app.state.session_service)
    prepared = await service.prepare_call(
        user_id=learner.user_id,
        session_id=session_id,
        model_alias=settings.openai_realtime_model,
        voice_alias=settings.openai_realtime_voice,
    )
    safety_id = hmac_new(
        secret.get_secret_value().encode(), str(learner.user_id).encode(), sha256
    ).hexdigest()
    try:
        created = await provider.create_call(
            offer_sdp=offer,
            instructions=prepared.instructions,
            model=prepared.model_alias,
            voice=prepared.voice_alias,
            safety_identifier=safety_id,
            client_request_id=str(prepared.attempt_id),
        )
    except DefinitiveProviderFailure as error:
        await service.record_provider_failure(attempt_id=prepared.attempt_id, ambiguous=False)
        raise VoiceProviderUnavailable from error
    except AmbiguousProviderFailure as error:
        await service.record_provider_failure(
            attempt_id=prepared.attempt_id, ambiguous=True, provider_call_id=error.call_id
        )
        raise VoiceProviderUnavailable from error
    except Exception as error:
        await service.record_provider_failure(attempt_id=prepared.attempt_id, ambiguous=True)
        raise VoiceProviderUnavailable from error
    try:
        deadline = await service.record_provider_call(
            attempt_id=prepared.attempt_id,
            provider_call_id=created.call_id,
            live_cap_seconds=1200 if settings.environment == Environment.PRODUCTION else 120,
        )
    except Exception:
        with suppress(AmbiguousProviderFailure):
            await provider.hangup(created.call_id)
        raise
    if deadline is None:
        raise VoiceProviderUnavailable
    return PlainTextResponse(
        created.answer_sdp,
        headers={
            "X-Call-Attempt-ID": str(prepared.attempt_id),
            "X-Call-Deadline-At": deadline.isoformat(),
            "Cache-Control": "no-store",
        },
        media_type="application/sdp",
    )


@router.post("/{session_id}/connections/{attempt_id}/ack", status_code=204)
async def acknowledge_connection(request: Request, session_id: UUID, attempt_id: UUID) -> Response:
    token = session_token(request)
    verify_csrf(request, token)
    learner = await cast(UserService, request.app.state.user_service).current_learner(
        session_token=token
    )
    service = cast(SessionService, request.app.state.session_service)
    await service.wait_for_sideband(
        user_id=learner.user_id, session_id=session_id, attempt_id=attempt_id
    )
    await service.acknowledge_call(
        user_id=learner.user_id, session_id=session_id, attempt_id=attempt_id
    )
    return Response(status_code=204)


@router.post("/{session_id}/end", status_code=204)
async def end_session(request: Request, session_id: UUID) -> Response:
    token = session_token(request)
    verify_csrf(request, token)
    learner = await cast(UserService, request.app.state.user_service).current_learner(
        session_token=token
    )
    await cast(SessionService, request.app.state.session_service).request_end(
        user_id=learner.user_id, session_id=session_id
    )
    return Response(status_code=204)
