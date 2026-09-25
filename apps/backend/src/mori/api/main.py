"""FastAPI application factory for the Mori API process."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware.trustedhost import TrustedHostMiddleware

from mori.api.errors import install_exception_handlers
from mori.api.middleware import security_headers_middleware
from mori.config import Environment, Settings
from mori.db import create_engine, create_session_maker
from mori.modules.identity.application import IdentityService
from mori.modules.identity.google import GoogleOIDC
from mori.modules.identity.persistence import SqlAlchemyIdentityUnitOfWorkFactory
from mori.modules.identity.ports import GoogleOIDCClient
from mori.modules.identity.routes import router as identity_router
from mori.modules.sessions.application import SessionService
from mori.modules.sessions.routes import router as session_router


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
    google_client = google or GoogleOIDC(
        client_id=runtime_settings.google_client_id,
        client_secret=runtime_settings.google_client_secret.get_secret_value(),
        redirect_uri=runtime_settings.google_redirect_uri,
    )
    service = IdentityService(
        unit_of_work_factory=SqlAlchemyIdentityUnitOfWorkFactory(session_maker),
        google=google_client,
        session_key=runtime_settings.session_signing_key.get_secret_value(),
        oauth_state_key=runtime_settings.oauth_state_key.get_secret_value(),
        session_ttl=timedelta(seconds=runtime_settings.auth_session_ttl_seconds),
        oauth_attempt_ttl=timedelta(seconds=runtime_settings.oauth_attempt_ttl_seconds),
        allowed_return_paths=runtime_settings.auth_return_paths,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
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
    app.state.session_service = SessionService(
        session_maker=session_maker,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[runtime_settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Idempotency-Key", "If-Match", "X-CSRF-Token"],
        expose_headers=["ETag", "Location", "X-Request-ID"],
    )
    allowed_hosts = [runtime_settings.api_host]
    if runtime_settings.environment == Environment.TEST:
        allowed_hosts.append("testserver")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.middleware("http")(security_headers_middleware)
    install_exception_handlers(app)
    app.include_router(identity_router)
    app.include_router(session_router)

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
