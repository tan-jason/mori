"""Cookie authentication and origin-bound CSRF verification for API routes."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from mori.config import Settings
from mori.modules.identity.application import IdentityService
from mori.modules.identity.errors import AuthenticationRequired, CsrfRejected
from mori.modules.identity.security import tokens_match


def session_token(request: Request) -> str:
    settings = cast(Settings, request.app.state.settings)
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AuthenticationRequired
    return token


def verify_csrf(request: Request, token: str) -> None:
    settings = cast(Settings, request.app.state.settings)
    if request.headers.get("origin") != settings.web_origin:
        raise CsrfRejected
    service = cast(IdentityService, request.app.state.identity_service)
    provided = request.headers.get("x-csrf-token", "")
    if not provided or not tokens_match(provided, service.csrf_token(token)):
        raise CsrfRejected
