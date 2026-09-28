"""PostgreSQL adapter for authentication and application sessions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mori.modules.identity.domain import ApplicationSession, OAuthLoginAttempt
from mori.modules.identity.errors import AuthenticationRequired, InvalidOAuthFlow
from mori.modules.identity.models import (
    AuthSessionModel,
    ExternalIdentityModel,
    OAuthLoginAttemptModel,
)


class SqlAlchemyIdentityStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_oauth_attempt(
        self,
        *,
        state_digest: str,
        nonce: str,
        code_verifier: str,
        return_path: str,
        now: datetime,
        expires_at: datetime,
    ) -> None:
        self._session.add(
            OAuthLoginAttemptModel(
                state_digest=state_digest,
                nonce=nonce,
                code_verifier=code_verifier,
                return_path=return_path,
                created_at=now,
                expires_at=expires_at,
            )
        )

    async def consume_oauth_attempt(
        self,
        *,
        state_digest: str,
        now: datetime,
    ) -> OAuthLoginAttempt:
        attempt = await self._session.scalar(
            select(OAuthLoginAttemptModel)
            .where(OAuthLoginAttemptModel.state_digest == state_digest)
            .with_for_update()
        )
        if attempt is None or attempt.consumed_at is not None or attempt.expires_at <= now:
            raise InvalidOAuthFlow

        attempt.consumed_at = now
        return OAuthLoginAttempt(
            nonce=attempt.nonce,
            code_verifier=attempt.code_verifier,
            return_path=attempt.return_path,
        )

    async def add_auth_session(
        self,
        *,
        user_id: UUID,
        token_digest: str,
        now: datetime,
        expires_at: datetime,
    ) -> ApplicationSession:
        model = AuthSessionModel(
            user_id=user_id,
            token_digest=token_digest,
            created_at=now,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        return ApplicationSession(id=model.id, user_id=user_id, expires_at=expires_at)

    async def revoke_auth_session(
        self,
        *,
        token_digest: str,
        now: datetime,
    ) -> None:
        session = await self._session.scalar(
            select(AuthSessionModel)
            .where(AuthSessionModel.token_digest == token_digest)
            .with_for_update()
        )
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            raise AuthenticationRequired
        session.revoked_at = now

    async def lock_google_subject(self, subject: str) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity_key, 0))"),
            {"identity_key": f"google:{subject}"},
        )

    async def google_user_id(self, subject: str) -> UUID | None:
        identity = await self._session.scalar(
            select(ExternalIdentityModel).where(
                ExternalIdentityModel.provider == "google",
                ExternalIdentityModel.subject == subject,
            )
        )
        return identity.user_id if identity is not None else None

    async def link_google_user(self, *, subject: str, user_id: UUID, now: datetime) -> None:
        identity = await self._session.scalar(
            select(ExternalIdentityModel).where(
                ExternalIdentityModel.provider == "google",
                ExternalIdentityModel.subject == subject,
            )
        )
        if identity is None:
            self._session.add(
                ExternalIdentityModel(
                    user_id=user_id,
                    provider="google",
                    subject=subject,
                    last_authenticated_at=now,
                    created_at=now,
                )
            )
        elif identity.user_id != user_id:
            raise RuntimeError("external identity changed account")
        else:
            identity.last_authenticated_at = now
        await self._session.flush()

    async def authenticated_user_id(self, *, token_digest: str, now: datetime) -> UUID:
        user_id = await self._session.scalar(
            select(AuthSessionModel.user_id).where(
                AuthSessionModel.token_digest == token_digest,
                AuthSessionModel.revoked_at.is_(None),
                AuthSessionModel.expires_at > now,
            )
        )
        if user_id is None:
            raise AuthenticationRequired
        return user_id
