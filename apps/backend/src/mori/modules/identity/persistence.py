"""PostgreSQL adapter for identity application ports."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction, async_sessionmaker

from mori.modules.access.constants import INTRO_PLAN_VERSION_ID
from mori.modules.access.models import GrantModel
from mori.modules.identity.domain import (
    ApplicationSession,
    CorrectionPreference,
    CurrentLearner,
    GoogleClaims,
    LanguageProfileStatus,
    LanguageProfileView,
    OAuthLoginAttempt,
    PreferenceChanges,
    PreferencesView,
    TutorPace,
    UserStatus,
)
from mori.modules.identity.errors import (
    AccountUnavailable,
    AuthenticationRequired,
    InvalidOAuthFlow,
    PreferenceVersionConflict,
)
from mori.modules.identity.models import (
    AuthSessionModel,
    ExternalIdentityModel,
    LanguageProfileModel,
    LearnerPreferenceModel,
    OAuthLoginAttemptModel,
    UserModel,
)
from mori.modules.identity.ports import IdentityUnitOfWork


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

    async def provision_google_user(self, *, claims: GoogleClaims, now: datetime) -> UUID:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identity_key, 0))"),
            {"identity_key": f"google:{claims.subject}"},
        )

        identity = await self._session.scalar(
            select(ExternalIdentityModel).where(
                ExternalIdentityModel.provider == "google",
                ExternalIdentityModel.subject == claims.subject,
            )
        )

        if identity is None:
            user = UserModel(
                status=UserStatus.ACTIVE.value,
                email=claims.email,
                display_name=claims.display_name,
                created_at=now,
                updated_at=now,
            )
            self._session.add(user)
            await self._session.flush()
            identity = ExternalIdentityModel(
                user_id=user.id,
                provider="google",
                subject=claims.subject,
                last_authenticated_at=now,
                created_at=now,
            )
            self._session.add(identity)
        else:
            existing_user = await self._session.get(UserModel, identity.user_id)
            if existing_user is None:
                raise RuntimeError("external identity has no user")
            user = existing_user
            if user.status != UserStatus.ACTIVE.value:
                raise AccountUnavailable
            user.email = claims.email
            user.display_name = claims.display_name
            user.updated_at = now
            identity.last_authenticated_at = now

        profile = await self._session.scalar(
            select(LanguageProfileModel).where(
                LanguageProfileModel.user_id == user.id,
                LanguageProfileModel.base_language_id == "english",
                LanguageProfileModel.target_language_id == "mandarin",
            )
        )
        if profile is None:
            profile = LanguageProfileModel(
                user_id=user.id,
                base_language_id="english",
                target_language_id="mandarin",
                status=LanguageProfileStatus.ACTIVE.value,
                created_at=now,
            )
            self._session.add(profile)
            await self._session.flush()

        preferences = await self._session.get(LearnerPreferenceModel, profile.id)
        if preferences is None:
            self._session.add(
                LearnerPreferenceModel(
                    language_profile_id=profile.id,
                    correction_preference=CorrectionPreference.BALANCED.value,
                    tutor_pace=TutorPace.LEVEL.value,
                    captions_enabled=False,
                    timezone="America/New_York",
                    version=1,
                    updated_at=now,
                )
            )

        intro_grant = await self._session.scalar(
            select(GrantModel).where(
                GrantModel.user_id == user.id,
                GrantModel.grant_type == "intro",
            )
        )
        if intro_grant is None:
            self._session.add(
                GrantModel(
                    user_id=user.id,
                    plan_version_id=INTRO_PLAN_VERSION_ID,
                    grant_type="intro",
                    status="active",
                    valid_from=now,
                    created_at=now,
                )
            )

        await self._session.flush()
        return user.id

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

    async def current_learner(
        self,
        *,
        token_digest: str,
        now: datetime,
    ) -> CurrentLearner:
        row = (
            await self._session.execute(
                select(UserModel, LanguageProfileModel, LearnerPreferenceModel)
                .join(AuthSessionModel, AuthSessionModel.user_id == UserModel.id)
                .join(LanguageProfileModel, LanguageProfileModel.user_id == UserModel.id)
                .join(
                    LearnerPreferenceModel,
                    LearnerPreferenceModel.language_profile_id == LanguageProfileModel.id,
                )
                .where(
                    AuthSessionModel.token_digest == token_digest,
                    AuthSessionModel.revoked_at.is_(None),
                    AuthSessionModel.expires_at > now,
                    LanguageProfileModel.status == LanguageProfileStatus.ACTIVE.value,
                )
            )
        ).one_or_none()
        if row is None:
            raise AuthenticationRequired

        user, profile, preferences = row
        if user.status != UserStatus.ACTIVE.value:
            raise AccountUnavailable
        return self._to_current_learner(user, profile, preferences)

    async def update_preferences(
        self,
        *,
        token_digest: str,
        expected_version: int,
        changes: PreferenceChanges,
        now: datetime,
    ) -> CurrentLearner:
        row = (
            await self._session.execute(
                select(UserModel, LanguageProfileModel, LearnerPreferenceModel)
                .join(AuthSessionModel, AuthSessionModel.user_id == UserModel.id)
                .join(LanguageProfileModel, LanguageProfileModel.user_id == UserModel.id)
                .join(
                    LearnerPreferenceModel,
                    LearnerPreferenceModel.language_profile_id == LanguageProfileModel.id,
                )
                .where(
                    AuthSessionModel.token_digest == token_digest,
                    AuthSessionModel.revoked_at.is_(None),
                    AuthSessionModel.expires_at > now,
                    LanguageProfileModel.status == LanguageProfileStatus.ACTIVE.value,
                )
                .with_for_update(of=LearnerPreferenceModel)
            )
        ).one_or_none()
        if row is None:
            raise AuthenticationRequired

        user, profile, preferences = row
        if user.status != UserStatus.ACTIVE.value:
            raise AccountUnavailable
        if preferences.version != expected_version:
            raise PreferenceVersionConflict

        if changes.correction_preference is not None:
            preferences.correction_preference = changes.correction_preference.value
        if changes.tutor_pace is not None:
            preferences.tutor_pace = changes.tutor_pace.value
        if changes.captions_enabled is not None:
            preferences.captions_enabled = changes.captions_enabled
        if changes.timezone is not None:
            preferences.timezone = changes.timezone
        preferences.version += 1
        preferences.updated_at = now
        await self._session.flush()
        return self._to_current_learner(user, profile, preferences)

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

    @staticmethod
    def _to_current_learner(
        user: UserModel,
        profile: LanguageProfileModel,
        preferences: LearnerPreferenceModel,
    ) -> CurrentLearner:
        return CurrentLearner(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=UserStatus(user.status),
            onboarding_complete=user.onboarding_completed_at is not None,
            language_profile=LanguageProfileView(
                id=profile.id,
                base_language_id=profile.base_language_id,
                target_language_id=profile.target_language_id,
                status=LanguageProfileStatus(profile.status),
            ),
            preferences=PreferencesView(
                correction_preference=CorrectionPreference(preferences.correction_preference),
                tutor_pace=TutorPace(preferences.tutor_pace),
                captions_enabled=preferences.captions_enabled,
                timezone=preferences.timezone,
                version=preferences.version,
            ),
        )


class SqlAlchemyIdentityUnitOfWork:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker
        self._session: AsyncSession | None = None
        self._transaction: AsyncSessionTransaction | None = None
        self._identity: SqlAlchemyIdentityStore | None = None

    @property
    def identity(self) -> SqlAlchemyIdentityStore:
        if self._identity is None:
            raise RuntimeError("unit of work has not been entered")
        return self._identity

    async def __aenter__(self) -> SqlAlchemyIdentityUnitOfWork:
        self._session = self._session_maker()
        self._transaction = await self._session.begin()
        self._identity = SqlAlchemyIdentityStore(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._transaction is None or self._session is None:
            return
        try:
            if exc_type is None:
                await self._transaction.commit()
            else:
                await self._transaction.rollback()
        finally:
            await self._session.close()


class SqlAlchemyIdentityUnitOfWorkFactory:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    def __call__(self) -> IdentityUnitOfWork:
        return SqlAlchemyIdentityUnitOfWork(self._session_maker)
