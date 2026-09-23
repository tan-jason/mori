"""Google-specific Authlib adapter tests."""

from __future__ import annotations

from typing import Any

import pytest

from mori.modules.identity.errors import OAuthProviderFailure
from mori.modules.identity.google import GoogleOIDC


class FakeAuthlibClient:
    def __init__(self, user_info: dict[str, Any]) -> None:
        self.user_info = user_info
        self.authorization_arguments: dict[str, str] | None = None
        self.exchange_arguments: dict[str, str] | None = None
        self.parsed_nonce: str | None = None

    async def create_authorization_url(self, redirect_uri: str, **kwargs: str) -> dict[str, str]:
        self.authorization_arguments = {"redirect_uri": redirect_uri, **kwargs}
        return {"url": "https://accounts.google.test/authorize"}

    async def fetch_access_token(self, **kwargs: str) -> dict[str, str]:
        self.exchange_arguments = kwargs
        return {"id_token": "signed-google-id-token", "access_token": "ephemeral-token"}

    async def parse_id_token(
        self,
        _token: dict[str, str],
        *,
        nonce: str,
    ) -> dict[str, Any]:
        self.parsed_nonce = nonce
        return self.user_info


def _google_with_client(client: FakeAuthlibClient) -> GoogleOIDC:
    google = GoogleOIDC(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost:8000/auth/google/callback",
    )
    google._client = client  # type: ignore[attr-defined]
    return google


@pytest.mark.asyncio
async def test_google_adapter_passes_pkce_state_and_nonce_to_authlib() -> None:
    authlib_client = FakeAuthlibClient(
        {
            "sub": "google-subject",
            "email": "learner@example.com",
            "email_verified": True,
            "name": "Learner",
        }
    )
    google = _google_with_client(authlib_client)

    url = await google.authorization_url(
        state="state-value",
        nonce="nonce-value",
        code_verifier="code-verifier-value",
    )
    claims = await google.exchange_code(
        code="authorization-code",
        nonce="nonce-value",
        code_verifier="code-verifier-value",
    )

    assert url == "https://accounts.google.test/authorize"
    assert authlib_client.authorization_arguments == {
        "redirect_uri": "http://localhost:8000/auth/google/callback",
        "state": "state-value",
        "nonce": "nonce-value",
        "code_verifier": "code-verifier-value",
    }
    assert authlib_client.exchange_arguments == {
        "redirect_uri": "http://localhost:8000/auth/google/callback",
        "code": "authorization-code",
        "code_verifier": "code-verifier-value",
    }
    assert authlib_client.parsed_nonce == "nonce-value"
    assert claims.subject == "google-subject"
    assert claims.email == "learner@example.com"


@pytest.mark.asyncio
async def test_google_adapter_rejects_unverified_email() -> None:
    google = _google_with_client(
        FakeAuthlibClient(
            {
                "sub": "google-subject",
                "email": "learner@example.com",
                "email_verified": False,
                "name": "Learner",
            }
        )
    )

    with pytest.raises(OAuthProviderFailure):
        await google.exchange_code(
            code="authorization-code",
            nonce="nonce-value",
            code_verifier="code-verifier-value",
        )
