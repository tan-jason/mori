"""HTTP routes for Google sign-in and application sessions."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from mori.api.auth import session_token as _session_token
from mori.api.auth import verify_csrf as _verify_csrf
from mori.api.contracts import mutation_headers
from mori.config import Settings
from mori.modules.identity.application import IdentityService
from mori.modules.identity.errors import InvalidOAuthFlow
from mori.modules.identity.security import tokens_match

router = APIRouter()


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _service(request: Request) -> IdentityService:
    return cast(IdentityService, request.app.state.identity_service)


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


@router.post("/auth/logout", status_code=204, openapi_extra=mutation_headers())
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
