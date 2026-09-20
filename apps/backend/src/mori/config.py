"""Validated application configuration."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


_ROOT_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or the ignored root .env."""

    model_config = SettingsConfigDict(
        env_file=_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Environment = Field(default=Environment.DEVELOPMENT, alias="MORI_ENV")
    api_origin: str = Field(default="http://localhost:8000", alias="API_ORIGIN")
    web_origin: str = Field(default="http://localhost:5173", alias="WEB_ORIGIN")
    database_url: str = Field(alias="DATABASE_URL")

    google_client_id: str = Field(alias="GOOGLE_CLIENT_ID", min_length=1)
    google_client_secret: SecretStr = Field(alias="GOOGLE_CLIENT_SECRET", min_length=1)
    google_redirect_uri: str = Field(alias="GOOGLE_REDIRECT_URI")
    session_signing_key: SecretStr = Field(alias="SESSION_SIGNING_KEY")
    oauth_state_key: SecretStr = Field(alias="OAUTH_STATE_KEY")

    auth_session_ttl_seconds: int = Field(
        default=30 * 24 * 60 * 60,
        alias="AUTH_SESSION_TTL_SECONDS",
        ge=300,
        le=90 * 24 * 60 * 60,
    )
    oauth_attempt_ttl_seconds: int = Field(
        default=10 * 60,
        alias="OAUTH_ATTEMPT_TTL_SECONDS",
        ge=60,
        le=30 * 60,
    )
    auth_return_paths: tuple[str, ...] = Field(default=("/",), alias="AUTH_RETURN_PATHS")

    @field_validator("api_origin", "web_origin", "google_redirect_uri")
    @classmethod
    def validate_absolute_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be an absolute HTTP URL")
        if parsed.query or parsed.fragment:
            raise ValueError("must not contain a query or fragment")
        return value.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("must use the postgresql+psycopg SQLAlchemy driver")
        return value

    @field_validator("session_signing_key", "oauth_state_key")
    @classmethod
    def validate_secret_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("must contain at least 32 characters")
        return value

    @field_validator("auth_return_paths")
    @classmethod
    def validate_return_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("must contain at least one path")
        for value in values:
            parsed = urlsplit(value)
            if not value.startswith("/") or value.startswith("//"):
                raise ValueError("must contain only absolute application paths")
            if parsed.scheme or parsed.netloc or parsed.fragment:
                raise ValueError("must contain only absolute application paths")
        return values

    @model_validator(mode="after")
    def validate_deployed_security(self) -> Settings:
        if self.environment in {Environment.STAGING, Environment.PRODUCTION}:
            for field_name, value in (
                ("API_ORIGIN", self.api_origin),
                ("WEB_ORIGIN", self.web_origin),
                ("GOOGLE_REDIRECT_URI", self.google_redirect_uri),
            ):
                if urlsplit(value).scheme != "https":
                    raise ValueError(f"{field_name} must use HTTPS outside local environments")
        return self

    @property
    def session_cookie_name(self) -> str:
        if self.environment in {Environment.STAGING, Environment.PRODUCTION}:
            return "__Host-mori_session"
        return "mori_session"

    @property
    def oauth_state_cookie_name(self) -> str:
        if self.environment in {Environment.STAGING, Environment.PRODUCTION}:
            return "__Host-mori_oauth_state"
        return "mori_oauth_state"

    @property
    def secure_cookies(self) -> bool:
        return self.environment in {Environment.STAGING, Environment.PRODUCTION}

    @property
    def api_host(self) -> str:
        host = urlsplit(self.api_origin).hostname
        if host is None:
            raise RuntimeError("API_ORIGIN has no host")
        return host
