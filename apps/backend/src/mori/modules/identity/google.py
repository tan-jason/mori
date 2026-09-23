"""Authlib adapter for Google OpenID Connect."""

from __future__ import annotations

from typing import Any

from authlib.integrations.starlette_client import OAuth  # type: ignore[import-untyped]

from mori.modules.identity.domain import GoogleClaims
from mori.modules.identity.errors import OAuthProviderFailure

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


class GoogleOIDC:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        registry = OAuth()
        client = registry.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url=GOOGLE_DISCOVERY_URL,
            client_kwargs={
                "scope": "openid email profile",
                "code_challenge_method": "S256",
            },
        )
        if client is None:
            raise RuntimeError("failed to configure Google OIDC client")
        self._client: Any = client
        self._redirect_uri = redirect_uri

    async def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str:
        try:
            result = await self._client.create_authorization_url(
                self._redirect_uri,
                state=state,
                nonce=nonce,
                code_verifier=code_verifier,
            )
            return str(result["url"])
        except Exception as error:
            raise OAuthProviderFailure from error

    async def exchange_code(
        self,
        *,
        code: str,
        nonce: str,
        code_verifier: str,
    ) -> GoogleClaims:
        try:
            token = await self._client.fetch_access_token(
                redirect_uri=self._redirect_uri,
                code=code,
                code_verifier=code_verifier,
            )
            user_info = await self._client.parse_id_token(token, nonce=nonce)
            subject = user_info.get("sub")
            email = user_info.get("email")
            email_verified = user_info.get("email_verified") is True
            display_name = user_info.get("name")
            if not isinstance(subject, str) or not subject:
                raise ValueError("Google ID token has no subject")
            if not isinstance(email, str) or not email or not email_verified:
                raise ValueError("Google account email is not verified")
            if not isinstance(display_name, str) or not display_name.strip():
                display_name = email.partition("@")[0]
            return GoogleClaims(
                subject=subject,
                email=email,
                email_verified=True,
                display_name=display_name.strip(),
            )
        except Exception as error:
            raise OAuthProviderFailure from error
