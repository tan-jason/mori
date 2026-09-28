"""Authentication ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from mori.modules.identity.domain import ApplicationSession, GoogleClaims, OAuthLoginAttempt


class GoogleOIDCClient(Protocol):
    async def authorization_url(self, *, state: str, nonce: str, code_verifier: str) -> str: ...

    async def exchange_code(self, *, code: str, nonce: str, code_verifier: str) -> GoogleClaims: ...


class IdentityStore(Protocol):
    async def add_oauth_attempt(
        self,
        *,
        state_digest: str,
        nonce: str,
        code_verifier: str,
        return_path: str,
        now: datetime,
        expires_at: datetime,
    ) -> None: ...

    async def consume_oauth_attempt(
        self, *, state_digest: str, now: datetime
    ) -> OAuthLoginAttempt: ...

    async def lock_google_subject(self, subject: str) -> None: ...

    async def google_user_id(self, subject: str) -> UUID | None: ...

    async def link_google_user(self, *, subject: str, user_id: UUID, now: datetime) -> None: ...

    async def add_auth_session(
        self, *, user_id: UUID, token_digest: str, now: datetime, expires_at: datetime
    ) -> ApplicationSession: ...

    async def authenticated_user_id(self, *, token_digest: str, now: datetime) -> UUID: ...

    async def revoke_auth_session(self, *, token_digest: str, now: datetime) -> None: ...
