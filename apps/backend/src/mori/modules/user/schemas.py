"""HTTP models for the composed current learner view."""

from __future__ import annotations

from uuid import UUID

from pydantic import EmailStr, Field

from mori.api.schemas import ApiModel
from mori.modules.learner_profiles.schemas import (
    LanguageProfileResponse,
    LearningSettingsResponse,
    PreferencesResponse,
)
from mori.modules.user.domain import CurrentLearner, UserStatus


class UserResponse(ApiModel):
    id: UUID
    email: EmailStr
    display_name: str = Field(min_length=1)
    status: UserStatus


class OnboardingResponse(ApiModel):
    complete: bool


class MeResponse(ApiModel):
    user: UserResponse
    version: int = Field(gt=0)
    onboarding: OnboardingResponse
    active_language_profile: LanguageProfileResponse | None
    preferences: PreferencesResponse | None
    csrf_token: str = Field(min_length=1)

    @classmethod
    def from_domain(cls, learner: CurrentLearner, *, csrf_token: str) -> MeResponse:
        return cls(
            user=UserResponse(
                id=learner.user_id,
                email=learner.email,
                display_name=learner.display_name,
                status=learner.status,
            ),
            version=learner.version,
            onboarding=OnboardingResponse(complete=learner.onboarding_complete),
            active_language_profile=LanguageProfileResponse(
                id=learner.language_profile.id,
                base_language_id=learner.language_profile.base_language_id,
                target_language_id=learner.language_profile.target_language_id,
                status=learner.language_profile.status,
                language_selection_confirmed=learner.language_profile.language_selection_confirmed,
                version=learner.language_profile.version,
                learning=LearningSettingsResponse(
                    mode=learner.language_profile.mode,
                    starting_choice=learner.language_profile.starting_choice,
                    provisional_level=learner.language_profile.provisional_level,
                    version=learner.language_profile.learning_settings_version,
                ),
            )
            if learner.language_profile is not None
            else None,
            preferences=PreferencesResponse(
                correction_preference=learner.preferences.correction_preference,
                tutor_pace=learner.preferences.tutor_pace,
                captions_enabled=learner.preferences.captions_enabled,
                timezone=learner.preferences.timezone,
                interests=list(learner.preferences.interests),
                learning_goal=learner.preferences.learning_goal,
                speaking_context=learner.preferences.speaking_context,
                learning_notes=learner.preferences.learning_notes,
                version=learner.preferences.version,
            )
            if learner.preferences is not None
            else None,
            csrf_token=csrf_token,
        )
