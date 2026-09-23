"""Stable HTTP error envelope and exception mapping."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from mori.modules.identity.errors import (
    AccountUnavailable,
    AuthenticationRequired,
    CsrfRejected,
    InvalidOAuthFlow,
    InvalidPrecondition,
    InvalidReturnPath,
    OAuthProviderFailure,
    PreconditionRequired,
    PreferenceVersionConflict,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ErrorDefinition:
    status: int
    code: str
    message: str


_EXPECTED_ERRORS: dict[type[Exception], ErrorDefinition] = {
    AuthenticationRequired: ErrorDefinition(
        401, "authentication_required", "Authentication is required."
    ),
    AccountUnavailable: ErrorDefinition(403, "account_unavailable", "This account is unavailable."),
    CsrfRejected: ErrorDefinition(403, "csrf_rejected", "The request could not be verified."),
    InvalidOAuthFlow: ErrorDefinition(
        400, "invalid_oauth_flow", "The sign-in attempt is invalid or expired."
    ),
    InvalidReturnPath: ErrorDefinition(
        400, "invalid_return_path", "The sign-in destination is invalid."
    ),
    OAuthProviderFailure: ErrorDefinition(
        502, "identity_provider_failure", "Google sign-in could not be completed."
    ),
    PreconditionRequired: ErrorDefinition(
        428, "precondition_required", "An If-Match header is required."
    ),
    InvalidPrecondition: ErrorDefinition(
        400, "invalid_precondition", "The If-Match header is invalid."
    ),
    PreferenceVersionConflict: ErrorDefinition(
        412, "preference_version_conflict", "Preferences changed since they were read."
    ),
}


def error_response(request: Request, definition: ErrorDefinition) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=definition.status,
        content={
            "error": {
                "code": definition.code,
                "message": definition.message,
                "requestId": request_id,
            }
        },
        headers={"Cache-Control": "no-store"},
    )


def install_exception_handlers(app: FastAPI) -> None:
    for exception_type, definition in _EXPECTED_ERRORS.items():
        app.add_exception_handler(
            exception_type,
            _expected_error_handler(definition),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return error_response(
            request,
            ErrorDefinition(422, "invalid_request", "The request is invalid."),
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, error: HTTPException) -> JSONResponse:
        if error.status_code == 404:
            definition = ErrorDefinition(404, "not_found", "The requested resource was not found.")
        elif error.status_code == 405:
            definition = ErrorDefinition(405, "method_not_allowed", "The method is not allowed.")
        else:
            definition = ErrorDefinition(error.status_code, "http_error", "The request failed.")
        return error_response(request, definition)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, error: Exception) -> JSONResponse:
        await logger.aexception(
            "unhandled_request_error",
            request_id=getattr(request.state, "request_id", "unknown"),
            method=request.method,
            path=request.url.path,
            exception_type=type(error).__name__,
        )
        return error_response(
            request,
            ErrorDefinition(500, "internal_error", "An unexpected error occurred."),
        )

    logging.getLogger("authlib").setLevel(logging.WARNING)


def _expected_error_handler(
    definition: ErrorDefinition,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, _error: Exception) -> JSONResponse:
        return error_response(request, definition)

    return handler
