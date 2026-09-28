"""Identity application use cases and transaction boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from mori.modules.identity.errors import InvalidOAuthFlow, InvalidReturnPath, OAuthProviderFailure
from mori.modules.identity.ports import GoogleOIDCClient
from mori.modules.identity.security import csrf_token, keyed_digest, random_token
from mori.persistence.ports import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class CompletedSignIn:
    session_token: str
    csrf_token: str
    expires_at: datetime
    return_path: str


@dataclass(frozen=True, slots=True)
class StartedSignIn:
    authorization_url: str
    state: str


class IdentityService:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        google: GoogleOIDCClient,
        session_key: str,
        oauth_state_key: str,
        session_ttl: timedelta,
        oauth_attempt_ttl: timedelta,
        allowed_return_paths: tuple[str, ...],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._google = google
        self._session_key = session_key
        self._oauth_state_key = oauth_state_key
        self._session_ttl = session_ttl
        self._oauth_attempt_ttl = oauth_attempt_ttl
        self._allowed_return_paths = frozenset(allowed_return_paths)

    async def start_google_sign_in(self, *, return_path: str) -> StartedSignIn:
        if return_path not in self._allowed_return_paths:
            raise InvalidReturnPath

        now = datetime.now(UTC)
        state = random_token()
        nonce = random_token()
        code_verifier = random_token(64)
        digest = keyed_digest(state, self._oauth_state_key, purpose="oauth-state")
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.identity.add_oauth_attempt(
                state_digest=digest,
                nonce=nonce,
                code_verifier=code_verifier,
                return_path=return_path,
                now=now,
                expires_at=now + self._oauth_attempt_ttl,
            )

        return StartedSignIn(
            authorization_url=await self._google.authorization_url(
                state=state,
                nonce=nonce,
                code_verifier=code_verifier,
            ),
            state=state,
        )

    async def complete_google_sign_in(self, *, state: str, code: str) -> CompletedSignIn:
        if not state or not code:
            raise InvalidOAuthFlow

        now = datetime.now(UTC)
        digest = keyed_digest(state, self._oauth_state_key, purpose="oauth-state")
        async with self._unit_of_work_factory() as unit_of_work:
            attempt = await unit_of_work.identity.consume_oauth_attempt(
                state_digest=digest,
                now=now,
            )

        claims = await self._google.exchange_code(
            code=code,
            nonce=attempt.nonce,
            code_verifier=attempt.code_verifier,
        )
        if not claims.email_verified:
            raise OAuthProviderFailure

        session_token = random_token()
        session_digest = keyed_digest(
            session_token,
            self._session_key,
            purpose="application-session",
        )
        expires_at = now + self._session_ttl
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.identity.lock_google_subject(claims.subject)
            existing_user_id = await unit_of_work.identity.google_user_id(claims.subject)
            user_id = await unit_of_work.accounts.create_or_update(
                user_id=existing_user_id,
                email=claims.email,
                display_name=claims.display_name,
                now=now,
            )
            await unit_of_work.identity.link_google_user(
                subject=claims.subject, user_id=user_id, now=now
            )
            await unit_of_work.access.ensure_intro_grant(user_id=user_id, now=now)
            await unit_of_work.identity.add_auth_session(
                user_id=user_id,
                token_digest=session_digest,
                now=now,
                expires_at=expires_at,
            )

        return CompletedSignIn(
            session_token=session_token,
            csrf_token=csrf_token(session_token, self._session_key),
            expires_at=expires_at,
            return_path=attempt.return_path,
        )

    async def abandon_google_sign_in(self, *, state: str) -> None:
        if not state:
            raise InvalidOAuthFlow
        digest = keyed_digest(state, self._oauth_state_key, purpose="oauth-state")
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.identity.consume_oauth_attempt(
                state_digest=digest,
                now=datetime.now(UTC),
            )

    async def logout(self, *, session_token: str) -> None:
        digest = self.session_digest(session_token)
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.identity.revoke_auth_session(
                token_digest=digest,
                now=datetime.now(UTC),
            )

    def csrf_token(self, session_token: str) -> str:
        return csrf_token(session_token, self._session_key)

    def session_digest(self, session_token: str) -> str:
        if not session_token:
            return ""
        return keyed_digest(
            session_token,
            self._session_key,
            purpose="application-session",
        )
