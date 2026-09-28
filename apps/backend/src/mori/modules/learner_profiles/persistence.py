"""PostgreSQL adapter for language profiles and onboarding."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mori.modules.learner_profiles.domain import (
    CorrectionPreference,
    CreateProfile,
    LanguageProfileStatus,
    LanguageProfileView,
    LearningMode,
    PreferenceChanges,
    PreferencesView,
    StartingChoice,
    TutorPace,
)
from mori.modules.learner_profiles.errors import (
    OnboardingIdempotencyConflict,
    OnboardingRequired,
    PreferenceVersionConflict,
    ProfileAlreadyConfirmed,
)
from mori.modules.learner_profiles.models import (
    LanguageProfileModel,
    LearnerPreferenceModel,
    OnboardingCommandModel,
    ProfileLearningSettingsModel,
)


class SqlAlchemyLearnerProfileStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def current(
        self, user_id: UUID
    ) -> tuple[LanguageProfileView | None, PreferencesView | None]:
        profile = await self._session.scalar(
            select(LanguageProfileModel).where(
                LanguageProfileModel.user_id == user_id,
                LanguageProfileModel.status == LanguageProfileStatus.ACTIVE.value,
                LanguageProfileModel.language_selection_confirmed_at.is_not(None),
            )
        )
        if profile is None:
            return None, None
        preferences = await self._session.get(LearnerPreferenceModel, profile.id)
        settings = await self._session.get(ProfileLearningSettingsModel, profile.id)
        if preferences is None or settings is None:
            raise RuntimeError("confirmed profile has incomplete settings")
        return (
            LanguageProfileView(
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
                    if settings.provisional_level is not None
                    else None
                ),
                learning_settings_version=settings.version,
            ),
            PreferencesView(
                correction_preference=CorrectionPreference(preferences.correction_preference),
                tutor_pace=TutorPace(preferences.tutor_pace),
                captions_enabled=preferences.captions_enabled,
                timezone=preferences.timezone,
                interests=tuple(preferences.interests),
                version=preferences.version,
            ),
        )

    async def replay_exists(self, *, user_id: UUID, key_digest: str, payload_digest: str) -> bool:
        existing = await self._session.scalar(
            select(OnboardingCommandModel).where(
                OnboardingCommandModel.user_id == user_id,
                OnboardingCommandModel.key_digest == key_digest,
            )
        )
        if existing is None:
            return False
        if existing.payload_digest != payload_digest:
            raise OnboardingIdempotencyConflict
        return True

    async def confirm(
        self,
        *,
        user_id: UUID,
        command: CreateProfile,
        key_digest: str,
        payload_digest: str,
        now: datetime,
    ) -> None:
        current_active = await self._session.scalar(
            select(LanguageProfileModel).where(
                LanguageProfileModel.user_id == user_id,
                LanguageProfileModel.status == LanguageProfileStatus.ACTIVE.value,
            )
        )
        profile = await self._session.scalar(
            select(LanguageProfileModel).where(
                LanguageProfileModel.user_id == user_id,
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
                user_id=user_id,
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
            self._session.add(
                LearnerPreferenceModel(
                    language_profile_id=profile.id,
                    correction_preference=command.correction_preference.value,
                    tutor_pace=command.tutor_pace.value,
                    captions_enabled=False,
                    timezone=command.timezone,
                    interests=list(command.interests),
                    version=1,
                    updated_at=now,
                )
            )
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

        self._session.add(
            OnboardingCommandModel(
                user_id=user_id,
                key_digest=key_digest,
                payload_digest=payload_digest,
                language_profile_id=profile.id,
                created_at=now,
            )
        )
        await self._session.flush()

    async def update_preferences(
        self,
        *,
        user_id: UUID,
        expected_version: int,
        changes: PreferenceChanges,
        now: datetime,
    ) -> None:
        row = (
            await self._session.execute(
                select(LanguageProfileModel, LearnerPreferenceModel)
                .join(
                    LearnerPreferenceModel,
                    LearnerPreferenceModel.language_profile_id == LanguageProfileModel.id,
                )
                .where(
                    LanguageProfileModel.user_id == user_id,
                    LanguageProfileModel.status == LanguageProfileStatus.ACTIVE.value,
                    LanguageProfileModel.language_selection_confirmed_at.is_not(None),
                )
                .with_for_update(of=LearnerPreferenceModel)
            )
        ).one_or_none()
        if row is None:
            raise OnboardingRequired
        _, preferences = row
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

    async def active_pair(self, *, user_id: UUID, profile_id: UUID) -> tuple[str, str] | None:
        profile = await self._session.scalar(
            select(LanguageProfileModel).where(
                LanguageProfileModel.id == profile_id,
                LanguageProfileModel.user_id == user_id,
                LanguageProfileModel.status == LanguageProfileStatus.ACTIVE.value,
                LanguageProfileModel.language_selection_confirmed_at.is_not(None),
            )
        )
        if profile is None:
            return None
        return profile.base_language_id, profile.target_language_id
