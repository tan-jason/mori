"""PostgreSQL and application fixtures for backend tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from testcontainers.community.postgres import PostgresContainer

from mori.api.main import create_app
from mori.config import Environment, Settings
from mori.modules.identity.domain import GoogleClaims

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class FakeGoogleOIDC:
    def __init__(self) -> None:
        self.claims = GoogleClaims(
            subject="google-subject-123",
            email="learner@example.com",
            email_verified=True,
            display_name="Mori Learner",
        )
        self.authorizations: dict[str, tuple[str, str]] = {}
        self.exchange_count = 0

    async def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str:
        self.authorizations[state] = (nonce, code_verifier)
        return f"https://accounts.google.test/authorize?state={state}"

    async def exchange_code(
        self,
        *,
        code: str,
        nonce: str,
        code_verifier: str,
    ) -> GoogleClaims:
        if code != "valid-code":
            raise AssertionError("unexpected authorization code")
        if (nonce, code_verifier) not in self.authorizations.values():
            raise AssertionError("login attempt values did not round-trip")
        self.exchange_count += 1
        return self.claims


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer(
        "postgres:17.8-bookworm",
        username="mori_test",
        password="mori_test_password",
        dbname="mori_test",
        driver="psycopg",
    ) as postgres:
        url = postgres.get_connection_url(driver="psycopg")
        alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_config, "head")
        yield url


@pytest.fixture(autouse=True)
def clean_database(database_url: str) -> Iterator[None]:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    user_consents,
                    auth_sessions,
                    oauth_login_attempts,
                    grants,
                    learner_preferences,
                    language_profiles,
                    external_identities,
                    users
                RESTART IDENTITY CASCADE
                """
            )
        )
    yield
    engine.dispose()


@pytest.fixture
def settings(database_url: str) -> Settings:
    secret = "test-secret-value-that-is-at-least-32-characters"
    return Settings(
        MORI_ENV=Environment.TEST,
        API_ORIGIN="http://testserver",
        WEB_ORIGIN="http://web.test",
        DATABASE_URL=database_url,
        GOOGLE_CLIENT_ID="google-client-id",
        GOOGLE_CLIENT_SECRET=secret,
        GOOGLE_REDIRECT_URI="http://testserver/auth/google/callback",
        SESSION_SIGNING_KEY=f"session-{secret}",
        OAUTH_STATE_KEY=f"oauth-{secret}",
    )


@pytest.fixture
def fake_google() -> FakeGoogleOIDC:
    return FakeGoogleOIDC()


@pytest.fixture
def app(settings: Settings, fake_google: FakeGoogleOIDC) -> FastAPI:
    return create_app(settings=settings, google=fake_google)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client
