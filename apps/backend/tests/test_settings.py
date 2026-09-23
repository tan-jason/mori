"""Configuration security invariant tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mori.config import Environment, Settings


def _settings_values() -> dict[str, object]:
    secret = "a-secure-test-secret-with-at-least-32-characters"
    return {
        "MORI_ENV": Environment.PRODUCTION,
        "API_ORIGIN": "https://api.mori.example",
        "WEB_ORIGIN": "https://mori.example",
        "DATABASE_URL": "postgresql+psycopg://mori:password@database/mori",
        "GOOGLE_CLIENT_ID": "client-id",
        "GOOGLE_CLIENT_SECRET": secret,
        "GOOGLE_REDIRECT_URI": "https://api.mori.example/auth/google/callback",
        "SESSION_SIGNING_KEY": f"session-{secret}",
        "OAUTH_STATE_KEY": f"oauth-{secret}",
    }


def test_production_uses_host_prefix_cookie() -> None:
    settings = Settings(**_settings_values())  # type: ignore[arg-type]

    assert settings.session_cookie_name == "__Host-mori_session"
    assert settings.oauth_state_cookie_name == "__Host-mori_oauth_state"
    assert settings.secure_cookies is True


def test_production_rejects_insecure_origins() -> None:
    values = _settings_values()
    values["WEB_ORIGIN"] = "http://mori.example"

    with pytest.raises(ValidationError):
        Settings(**values)  # type: ignore[arg-type]


def test_return_paths_cannot_be_protocol_relative() -> None:
    values = _settings_values()
    values["AUTH_RETURN_PATHS"] = ("//attacker.example",)

    with pytest.raises(ValidationError):
        Settings(**values)  # type: ignore[arg-type]
