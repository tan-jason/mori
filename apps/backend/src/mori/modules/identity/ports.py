"""Ports used by identity application use cases."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from mori.modules.identity.domain import (
    ApplicationSession,
    CurrentLearner,
    GoogleClaims,
    OAuthLoginAttempt,
    PreferenceChanges,
)


class GoogleOIDCClient(Protocol):
    async def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str: ...

    async def exchange_code(
        self,
        *,
        code: str,
        nonce: str,
        code_verifier: str,
    ) -> GoogleClaims: ...


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
        self,
        *,
        state_digest: str,
        now: datetime,
    ) -> OAuthLoginAttempt: ...

    async def provision_google_user(self, *, claims: GoogleClaims, now: datetime) -> UUID: ...

    async def add_auth_session(
        self,
        *,
        user_id: UUID,
        token_digest: str,
        now: datetime,
        expires_at: datetime,
    ) -> ApplicationSession: ...

    async def current_learner(
        self,
        *,
        token_digest: str,
        now: datetime,
    ) -> CurrentLearner: ...

    async def update_preferences(
        self,
        *,
        token_digest: str,
        expected_version: int,
        changes: PreferenceChanges,
        now: datetime,
    ) -> CurrentLearner: ...

    async def revoke_auth_session(
        self,
        *,
        token_digest: str,
        now: datetime,
    ) -> None: ...


class IdentityUnitOfWork(Protocol):
    @property
    def identity(self) -> IdentityStore: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class IdentityUnitOfWorkFactory(Protocol):
    def __call__(self) -> IdentityUnitOfWork: ...
