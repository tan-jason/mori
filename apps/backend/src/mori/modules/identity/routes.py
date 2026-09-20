"""FastAPI routes for Google sign-in and learner identity."""

from __future__ import annotations

import re
from typing import cast

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import RedirectResponse

from mori.config import Settings
from mori.modules.identity.application import IdentityService
from mori.modules.identity.errors import (
    AuthenticationRequired,
    CsrfRejected,
    InvalidOAuthFlow,
    InvalidPrecondition,
    PreconditionRequired,
)
from mori.modules.identity.schemas import MeResponse, PreferencePatch
from mori.modules.identity.security import tokens_match

router = APIRouter()
_ETAG_PATTERN = re.compile(r'^"([1-9][0-9]*)"$')


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _service(request: Request) -> IdentityService:
    return cast(IdentityService, request.app.state.identity_service)


def _session_token(request: Request) -> str:
    token = request.cookies.get(_settings(request).session_cookie_name)
    if not token:
        raise AuthenticationRequired
    return token


def _verify_csrf(request: Request, session_token: str) -> None:
    settings = _settings(request)
    if request.headers.get("origin") != settings.web_origin:
        raise CsrfRejected
    provided = request.headers.get("x-csrf-token", "")
    expected = _service(request).csrf_token(session_token)
    if not provided or not tokens_match(provided, expected):
        raise CsrfRejected


def _parse_etag(if_match: str | None) -> int:
    if if_match is None:
        raise PreconditionRequired
    match = _ETAG_PATTERN.fullmatch(if_match.strip())
    if match is None:
        raise InvalidPrecondition
    return int(match.group(1))


@router.get("/auth/google/start", include_in_schema=False)
async def start_google_sign_in(
    request: Request,
    return_to: str = Query(default="/"),
) -> RedirectResponse:
    result = await _service(request).start_google_sign_in(return_path=return_to)
    settings = _settings(request)
    response = RedirectResponse(result.authorization_url, status_code=302)
    response.set_cookie(
        key=settings.oauth_state_cookie_name,
        value=result.state,
        max_age=settings.oauth_attempt_ttl_seconds,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/auth/google/callback", include_in_schema=False)
async def complete_google_sign_in(
    request: Request,
    state: str | None = Query(default=None),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    service = _service(request)
    settings = _settings(request)
    browser_state = request.cookies.get(settings.oauth_state_cookie_name)
    if not state or not browser_state or not tokens_match(state, browser_state):
        raise InvalidOAuthFlow
    if error or not code:
        await service.abandon_google_sign_in(state=state)
        raise InvalidOAuthFlow

    result = await service.complete_google_sign_in(state=state, code=code)
    response = RedirectResponse(
        f"{settings.web_origin}{result.return_path}",
        status_code=302,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.session_token,
        max_age=settings.auth_session_ttl_seconds,
        expires=result.expires_at,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=settings.oauth_state_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/auth/logout", status_code=204)
async def logout(request: Request) -> Response:
    session_token = _session_token(request)
    _verify_csrf(request, session_token)
    await _service(request).logout(session_token=session_token)
    settings = _settings(request)
    response = Response(status_code=204)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/api/v1/me", response_model=MeResponse)
async def get_me(request: Request, response: Response) -> MeResponse:
    session_token = _session_token(request)
    service = _service(request)
    learner = await service.current_learner(session_token=session_token)
    response.headers["ETag"] = f'"{learner.preferences.version}"'
    return MeResponse.from_domain(
        learner,
        csrf_token=service.csrf_token(session_token),
    )


@router.patch("/api/v1/me/preferences", response_model=MeResponse)
async def update_preferences(
    request: Request,
    response: Response,
    patch: PreferencePatch,
    if_match: str | None = Header(default=None),
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
    response.headers["ETag"] = f'"{learner.preferences.version}"'
    return MeResponse.from_domain(
        learner,
        csrf_token=service.csrf_token(session_token),
    )
