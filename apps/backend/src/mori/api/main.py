"""FastAPI application factory for the Mori API process."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware.trustedhost import TrustedHostMiddleware

from mori.api.errors import ApiErrorResponse, install_exception_handlers
from mori.api.middleware import security_headers_middleware
from mori.config import Environment, Settings
from mori.db import create_engine, create_session_maker
from mori.modules.identity.application import IdentityService
from mori.modules.identity.google import GoogleOIDC
from mori.modules.identity.ports import GoogleOIDCClient
from mori.modules.identity.routes import router as identity_router
from mori.modules.learner_profiles.application import LearnerProfileService
from mori.modules.learner_profiles.routes import router as learner_profile_router
from mori.modules.sessions.application import SessionService
from mori.modules.sessions.realtime_provider import OpenAIRealtimeProvider
from mori.modules.sessions.routes import router as session_router
from mori.modules.sessions.supervisor import RealtimeSupervisor
from mori.modules.user.application import UserService
from mori.modules.user.routes import router as user_router
from mori.persistence.uow import SqlAlchemyUnitOfWorkFactory


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Uvicorn's default access log includes query strings, which would expose
    # OAuth callback codes and state. Safe request logging is handled by Mori.
    logging.getLogger("uvicorn.access").disabled = True
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def create_app(
    *,
    settings: Settings | None = None,
    google: GoogleOIDCClient | None = None,
    engine: AsyncEngine | None = None,
) -> FastAPI:
    _configure_logging()
    runtime_settings = settings or Settings()  # type: ignore[call-arg]
    runtime_engine = engine or create_engine(runtime_settings.database_url)
    session_maker = create_session_maker(runtime_engine)
    unit_of_work_factory = SqlAlchemyUnitOfWorkFactory(session_maker)
    google_client = google or GoogleOIDC(
        client_id=runtime_settings.google_client_id,
        client_secret=runtime_settings.google_client_secret.get_secret_value(),
        redirect_uri=runtime_settings.google_redirect_uri,
    )
    service = IdentityService(
        unit_of_work_factory=unit_of_work_factory,
        google=google_client,
        session_key=runtime_settings.session_signing_key.get_secret_value(),
        oauth_state_key=runtime_settings.oauth_state_key.get_secret_value(),
        session_ttl=timedelta(seconds=runtime_settings.auth_session_ttl_seconds),
        oauth_attempt_ttl=timedelta(seconds=runtime_settings.oauth_attempt_ttl_seconds),
        allowed_return_paths=runtime_settings.auth_return_paths,
    )

    # TODO(launch): Remove this testing bypass and enforce the one-time intro grant everywhere.
    session_service = SessionService(
        session_maker=session_maker,
        allow_repeated_intro_sessions=runtime_settings.environment != Environment.PRODUCTION,
    )
    api_key = runtime_settings.openai_api_key
    safety_secret = runtime_settings.openai_safety_id_secret
    provider = (
        OpenAIRealtimeProvider(api_key=api_key.get_secret_value())
        if api_key is not None and safety_secret is not None
        else None
    )
    supervisor = (
        RealtimeSupervisor(
            session_maker=session_maker,
            service=session_service,
            provider=provider,
            api_key=api_key.get_secret_value(),
        )
        if provider is not None and api_key is not None
        else None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if supervisor is not None:
            supervisor.start()
        try:
            yield
        finally:
            if supervisor is not None:
                await supervisor.stop()
            await runtime_engine.dispose()

    app = FastAPI(
        title="Mori API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if runtime_settings.environment != Environment.PRODUCTION else None,
        redoc_url=None,
    )
    app.state.settings = runtime_settings
    app.state.database_engine = runtime_engine
    app.state.session_maker = session_maker
    app.state.identity_service = service
    app.state.user_service = UserService(
        unit_of_work_factory=unit_of_work_factory, identity=service
    )
    app.state.learner_profile_service = LearnerProfileService(
        unit_of_work_factory=unit_of_work_factory, identity=service
    )
    app.state.session_service = session_service
    app.state.realtime_provider = provider
    app.state.realtime_supervisor = supervisor

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[runtime_settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Idempotency-Key", "If-Match", "X-CSRF-Token"],
        expose_headers=[
            "ETag", "Location", "X-Request-ID", "X-Call-Attempt-ID", "X-Call-Deadline-At"
        ],
    )
    allowed_hosts = [runtime_settings.api_host]
    if runtime_settings.environment == Environment.TEST:
        allowed_hosts.append("testserver")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.middleware("http")(security_headers_middleware)
    install_exception_handlers(app)
    error_contract: dict[int | str, dict[str, Any]] = {
        "default": {"model": ApiErrorResponse, "description": "Mori error envelope"}
    }
    app.include_router(identity_router, responses=error_contract)
    app.include_router(user_router, responses=error_contract)
    app.include_router(learner_profile_router, responses=error_contract)
    app.include_router(session_router, responses=error_contract)

    @app.get("/health", tags=["operations"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["operations"], response_model=None)
    async def ready() -> dict[str, str] | JSONResponse:
        try:
            async with session_maker() as session:
                await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            structlog.get_logger(__name__).warning("database_readiness_failed")
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ok"}

    return app
