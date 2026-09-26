"""Pydantic HTTP models for identity endpoints."""

from __future__ import annotations

from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from pydantic.alias_generators import to_camel
from pydantic.json_schema import SkipJsonSchema

from mori.modules.identity.domain import (
    CorrectionPreference,
    CurrentLearner,
    LanguageProfileStatus,
    PreferenceChanges,
    TutorPace,
    UserStatus,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class UserResponse(ApiModel):
    id: UUID
    email: EmailStr
    display_name: str = Field(min_length=1)
    status: UserStatus


class OnboardingResponse(ApiModel):
    complete: bool


class LanguageProfileResponse(ApiModel):
    id: UUID
    base_language_id: str
    target_language_id: str
    status: LanguageProfileStatus


class PreferencesResponse(ApiModel):
    correction_preference: CorrectionPreference
    tutor_pace: TutorPace
    captions_enabled: bool
    timezone: str = Field(min_length=1)
    version: int = Field(gt=0)


class MeResponse(ApiModel):
    user: UserResponse
    onboarding: OnboardingResponse
    active_language_profile: LanguageProfileResponse
    preferences: PreferencesResponse
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
            onboarding=OnboardingResponse(complete=learner.onboarding_complete),
            active_language_profile=LanguageProfileResponse(
                id=learner.language_profile.id,
                base_language_id=learner.language_profile.base_language_id,
                target_language_id=learner.language_profile.target_language_id,
                status=learner.language_profile.status,
            ),
            preferences=PreferencesResponse(
                correction_preference=learner.preferences.correction_preference,
                tutor_pace=learner.preferences.tutor_pace,
                captions_enabled=learner.preferences.captions_enabled,
                timezone=learner.preferences.timezone,
                version=learner.preferences.version,
            ),
            csrf_token=csrf_token,
        )


class PreferencePatch(ApiModel):
    correction_preference: CorrectionPreference | SkipJsonSchema[None] = None
    tutor_pace: TutorPace | SkipJsonSchema[None] = None
    captions_enabled: bool | SkipJsonSchema[None] = None
    timezone: str | SkipJsonSchema[None] = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_patch(self) -> PreferencePatch:
        fields_set = self.model_fields_set
        if not fields_set:
            raise ValueError("at least one preference is required")
        if any(getattr(self, field) is None for field in fields_set):
            raise ValueError("preferences cannot be null")
        if self.timezone is not None:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as error:
                raise ValueError("timezone must be a valid IANA timezone") from error
        return self

    def to_domain(self) -> PreferenceChanges:
        return PreferenceChanges(
            correction_preference=self.correction_preference,
            tutor_pace=self.tutor_pace,
            captions_enabled=self.captions_enabled,
            timezone=self.timezone,
        )
