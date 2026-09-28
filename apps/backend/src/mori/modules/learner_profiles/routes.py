"""HTTP routes for published pairs, onboarding, and preferences."""

from __future__ import annotations

import re
from typing import cast

from fastapi import APIRouter, Header, Request, Response

from mori.api.auth import session_token as _session_token
from mori.api.auth import verify_csrf as _verify_csrf
from mori.api.contracts import mutation_headers
from mori.modules.identity.application import IdentityService
from mori.modules.learner_profiles.application import LearnerProfileService
from mori.modules.learner_profiles.errors import (
    InvalidOnboardingKey,
    InvalidPrecondition,
    PreconditionRequired,
)
from mori.modules.learner_profiles.schemas import (
    CreateProfileRequest,
    LanguagePairResponse,
    LanguagePairsResponse,
    PreferencePatch,
)
from mori.modules.users.schemas import MeResponse

router = APIRouter()
_ETAG_PATTERN = re.compile(r'^"([1-9][0-9]*)"$')


def _service(request: Request) -> LearnerProfileService:
    return cast(LearnerProfileService, request.app.state.learner_profile_service)


def _identity(request: Request) -> IdentityService:
    return cast(IdentityService, request.app.state.identity_service)


def _parse_etag(if_match: str | None) -> int:
    if if_match is None:
        raise PreconditionRequired
    match = _ETAG_PATTERN.fullmatch(if_match.strip())
    if match is None:
        raise InvalidPrecondition
    return int(match.group(1))


@router.get("/api/v1/language-pairs", response_model=LanguagePairsResponse)
async def get_language_pairs(request: Request, response: Response) -> LanguagePairsResponse:
    response.headers["Cache-Control"] = "no-store"
    pairs = await _service(request).language_pairs()
    return LanguagePairsResponse(pairs=[LanguagePairResponse.from_domain(pair) for pair in pairs])


@router.post(
    "/api/v1/language-profiles",
    response_model=MeResponse,
    openapi_extra=mutation_headers("Idempotency-Key"),
)
async def create_language_profile(
    request: Request,
    response: Response,
    body: CreateProfileRequest,
    idempotency_key: str | None = Header(default=None, include_in_schema=False),
) -> MeResponse:
    session_token = _session_token(request)
    _verify_csrf(request, session_token)
    if idempotency_key is None:
        raise InvalidOnboardingKey
    service = _service(request)
    learner, created = await service.create_profile(
        session_token=session_token,
        idempotency_key=idempotency_key,
        command=body.to_domain(),
    )
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = f'"{learner.version}"'
    if learner.language_profile is not None:
        response.headers["Location"] = f"/api/v1/language-profiles/{learner.language_profile.id}"
    return MeResponse.from_domain(learner, csrf_token=_identity(request).csrf_token(session_token))


@router.patch(
    "/api/v1/me/preferences",
    response_model=MeResponse,
    openapi_extra=mutation_headers("If-Match"),
)
async def update_preferences(
    request: Request,
    response: Response,
    patch: PreferencePatch,
    if_match: str | None = Header(default=None, include_in_schema=False),
) -> MeResponse:
    session_token = _session_token(request)
    _verify_csrf(request, session_token)
    expected_version = _parse_etag(if_match)
    service = _service(request)
    learner = await service.update_preferences(
        session_token=session_token,
        expected_version=expected_version,
        changes=patch.to_domain(),
    )
    if learner.preferences is None:
        raise RuntimeError("updated profile has no preferences")
    response.headers["ETag"] = f'"{learner.preferences.version}"'
    return MeResponse.from_domain(
        learner,
        csrf_token=_identity(request).csrf_token(session_token),
    )
