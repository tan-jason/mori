"""PostgreSQL adapter for identity application ports."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from types import TracebackType
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction, async_sessionmaker

from mori.modules.access.constants import INTRO_PLAN_VERSION_ID
from mori.modules.access.models import GrantModel
from mori.modules.identity.domain import (
    ApplicationSession,
    CorrectionPreference,
    CoursePairView,
    CreateProfile,
    CurrentLearner,
    GoogleClaims,
    LanguageProfileStatus,
    LanguageProfileView,
    LearningMode,
    OAuthLoginAttempt,
    PreferenceChanges,
    PreferencesView,
    StartingChoice,
    TutorPace,
    UserStatus,
)
from mori.modules.identity.errors import (
    AccountUnavailable,
    AuthenticationRequired,
    InvalidOAuthFlow,
    InvalidOnboardingKey,
    OnboardingIdempotencyConflict,
    OnboardingRequired,
    PreferenceVersionConflict,
    ProfileAlreadyConfirmed,
    UnsupportedLanguagePair,
)
from mori.modules.identity.models import (
    AuthSessionModel,
    CourseCatalogModel,
    ExternalIdentityModel,
    LanguageProfileModel,
    LearnerPreferenceModel,
    OAuthLoginAttemptModel,
    OnboardingCommandModel,
    ProfileLearningSettingsModel,
    UserModel,
)
from mori.modules.identity.ports import IdentityUnitOfWork

_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_-]{7,127}\Z")


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
        user = await self._authenticated_user(token_digest=token_digest, now=now)
        return await self._learner_for_user(user)

    async def language_pairs(self) -> tuple[CoursePairView, ...]:
        rows = (
            await self._session.scalars(
                select(CourseCatalogModel).order_by(
                    CourseCatalogModel.base_language_name,
                    CourseCatalogModel.target_language_name,
                )
            )
        ).all()
        return tuple(
            CoursePairView(
                base_language_id=row.base_language_id,
                target_language_id=row.target_language_id,
                base_language_name=row.base_language_name,
                target_language_name=row.target_language_name,
                target_native_name=row.target_native_name,
                available=self._pair_available(row),
            )
            for row in rows
        )

    async def create_profile(
        self,
        *,
        token_digest: str,
        idempotency_key: str,
        command: CreateProfile,
        now: datetime,
    ) -> tuple[CurrentLearner, bool]:
        if not _KEY_PATTERN.fullmatch(idempotency_key):
            raise InvalidOnboardingKey
        user = await self._authenticated_user(token_digest=token_digest, now=now, lock=True)
        key_digest = sha256(idempotency_key.encode("ascii")).hexdigest()
        payload_digest = sha256(
            json.dumps(asdict(command), sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        existing_command = await self._session.scalar(
            select(OnboardingCommandModel).where(
                OnboardingCommandModel.user_id == user.id,
                OnboardingCommandModel.key_digest == key_digest,
            )
        )
        if existing_command is not None:
            if existing_command.payload_digest != payload_digest:
                raise OnboardingIdempotencyConflict
            return await self._learner_for_user(user), False

        pair = await self._session.scalar(
            select(CourseCatalogModel).where(
                CourseCatalogModel.base_language_id == command.base_language_id,
                CourseCatalogModel.target_language_id == command.target_language_id,
            )
        )
        if pair is None or not self._pair_available(pair):
            raise UnsupportedLanguagePair

        current_active = await self._session.scalar(
            select(LanguageProfileModel).where(
                LanguageProfileModel.user_id == user.id,
                LanguageProfileModel.status == LanguageProfileStatus.ACTIVE.value,
            )
        )
        profile = await self._session.scalar(
            select(LanguageProfileModel).where(
                LanguageProfileModel.user_id == user.id,
                LanguageProfileModel.base_language_id == command.base_language_id,
                LanguageProfileModel.target_language_id == command.target_language_id,
            )
        )
        if profile is not None and profile.language_selection_confirmed_at is not None:
            raise ProfileAlreadyConfirmed
        if current_active is not None and current_active is not profile:
            current_active.status = LanguageProfileStatus.ARCHIVED.value
            current_active.version += 1
            await self._session.flush()

        if profile is None:
            profile = LanguageProfileModel(
                user_id=user.id,
                base_language_id=command.base_language_id,
                target_language_id=command.target_language_id,
                status=LanguageProfileStatus.ACTIVE.value,
                language_selection_confirmed_at=now,
                version=1,
                created_at=now,
            )
            self._session.add(profile)
            await self._session.flush()
        else:
            profile.status = LanguageProfileStatus.ACTIVE.value
            profile.language_selection_confirmed_at = now
            profile.version += 1

        preferences = await self._session.get(LearnerPreferenceModel, profile.id)
        if preferences is None:
            preferences = LearnerPreferenceModel(
                language_profile_id=profile.id,
                correction_preference=command.correction_preference.value,
                tutor_pace=command.tutor_pace.value,
                captions_enabled=False,
                timezone=command.timezone,
                interests=list(command.interests),
                version=1,
                updated_at=now,
            )
            self._session.add(preferences)
        else:
            preferences.correction_preference = command.correction_preference.value
            preferences.tutor_pace = command.tutor_pace.value
            preferences.timezone = command.timezone
            preferences.interests = list(command.interests)
            preferences.version += 1
            preferences.updated_at = now

        settings = await self._session.get(ProfileLearningSettingsModel, profile.id)
        provisional = (
            None
            if command.starting_choice == StartingChoice.FLUENT
            else StartingChoice.BEGINNER
            if command.starting_choice == StartingChoice.UNSURE
            else command.starting_choice
        )
        mode = (
            LearningMode.PRACTICE
            if command.starting_choice == StartingChoice.FLUENT
            else LearningMode.LEARNING
        )
        if settings is None:
            self._session.add(
                ProfileLearningSettingsModel(
                    language_profile_id=profile.id,
                    starting_choice=command.starting_choice.value,
                    mode=mode.value,
                    provisional_level=provisional.value if provisional else None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            settings.starting_choice = command.starting_choice.value
            settings.mode = mode.value
            settings.provisional_level = provisional.value if provisional else None
            settings.version += 1
            settings.updated_at = now

        if user.onboarding_completed_at is None:
            user.onboarding_completed_at = now
        user.version += 1
        user.updated_at = now
        self._session.add(
            OnboardingCommandModel(
                user_id=user.id,
                key_digest=key_digest,
                payload_digest=payload_digest,
                language_profile_id=profile.id,
                created_at=now,
            )
        )
        await self._session.flush()
        return await self._learner_for_user(user), True

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
                    LanguageProfileModel.language_selection_confirmed_at.is_not(None),
                )
                .with_for_update(of=LearnerPreferenceModel)
            )
        ).one_or_none()
        if row is None:
            await self._authenticated_user(token_digest=token_digest, now=now)
            raise OnboardingRequired

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
        return await self._learner_for_user(user)

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

    async def _authenticated_user(
        self, *, token_digest: str, now: datetime, lock: bool = False
    ) -> UserModel:
        statement = (
            select(UserModel)
            .join(AuthSessionModel, AuthSessionModel.user_id == UserModel.id)
            .where(
                AuthSessionModel.token_digest == token_digest,
                AuthSessionModel.revoked_at.is_(None),
                AuthSessionModel.expires_at > now,
            )
        )
        if lock:
            statement = statement.with_for_update(of=UserModel)
        user = await self._session.scalar(statement)
        if user is None:
            raise AuthenticationRequired
        if user.status != UserStatus.ACTIVE.value:
            raise AccountUnavailable
        return user

    async def _learner_for_user(self, user: UserModel) -> CurrentLearner:
        profile = await self._session.scalar(
            select(LanguageProfileModel).where(
                LanguageProfileModel.user_id == user.id,
                LanguageProfileModel.status == LanguageProfileStatus.ACTIVE.value,
                LanguageProfileModel.language_selection_confirmed_at.is_not(None),
            )
        )
        preferences = (
            await self._session.get(LearnerPreferenceModel, profile.id)
            if profile is not None else None
        )
        settings = (
            await self._session.get(ProfileLearningSettingsModel, profile.id)
            if profile is not None else None
        )
        if profile is not None and (preferences is None or settings is None):
            raise RuntimeError("confirmed profile has incomplete settings")
        return CurrentLearner(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=UserStatus(user.status),
            onboarding_complete=user.onboarding_completed_at is not None and profile is not None,
            version=user.version,
            language_profile=LanguageProfileView(
                id=profile.id,
                base_language_id=profile.base_language_id,
                target_language_id=profile.target_language_id,
                status=LanguageProfileStatus(profile.status),
                language_selection_confirmed=True,
                version=profile.version,
                starting_choice=StartingChoice(settings.starting_choice),
                mode=LearningMode(settings.mode),
                provisional_level=(
                    StartingChoice(settings.provisional_level)
                    if settings.provisional_level is not None else None
                ),
                learning_settings_version=settings.version,
            ) if profile is not None and settings is not None else None,
            preferences=PreferencesView(
                correction_preference=CorrectionPreference(preferences.correction_preference),
                tutor_pace=TutorPace(preferences.tutor_pace),
                captions_enabled=preferences.captions_enabled,
                timezone=preferences.timezone,
                interests=tuple(preferences.interests),
                version=preferences.version,
            ) if preferences is not None else None,
        )

    @staticmethod
    def _pair_available(pair: CourseCatalogModel) -> bool:
        return (
            pair.status == "published"
            and pair.active_curriculum_version is not None
            and pair.pair_policy_version is not None
            and pair.voice_policy_version is not None
            and pair.published_at is not None
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
