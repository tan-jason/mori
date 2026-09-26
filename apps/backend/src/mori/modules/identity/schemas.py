"""Pydantic HTTP models for identity endpoints."""

from __future__ import annotations

from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from pydantic.alias_generators import to_camel
from pydantic.json_schema import SkipJsonSchema

from mori.modules.identity.domain import (
    CorrectionPreference,
    CoursePairView,
    CreateProfile,
    CurrentLearner,
    LanguageProfileStatus,
    LearningMode,
    PreferenceChanges,
    StartingChoice,
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
    language_selection_confirmed: bool
    version: int = Field(gt=0)
    learning: LearningSettingsResponse


class LearningSettingsResponse(ApiModel):
    mode: LearningMode
    starting_choice: StartingChoice
    provisional_level: StartingChoice | None
    version: int = Field(gt=0)


class PreferencesResponse(ApiModel):
    correction_preference: CorrectionPreference
    tutor_pace: TutorPace
    captions_enabled: bool
    timezone: str = Field(min_length=1)
    interests: list[str]
    version: int = Field(gt=0)


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
            ) if learner.language_profile is not None else None,
            preferences=PreferencesResponse(
                correction_preference=learner.preferences.correction_preference,
                tutor_pace=learner.preferences.tutor_pace,
                captions_enabled=learner.preferences.captions_enabled,
                timezone=learner.preferences.timezone,
                interests=list(learner.preferences.interests),
                version=learner.preferences.version,
            ) if learner.preferences is not None else None,
            csrf_token=csrf_token,
        )


class LanguagePairResponse(ApiModel):
    base_language_id: str
    target_language_id: str
    base_language_name: str
    target_language_name: str
    target_native_name: str
    available: bool

    @classmethod
    def from_domain(cls, pair: CoursePairView) -> LanguagePairResponse:
        return cls.model_validate(pair, from_attributes=True)


class LanguagePairsResponse(ApiModel):
    pairs: list[LanguagePairResponse]


class CreateProfileRequest(ApiModel):
    base_language_id: str = Field(min_length=1, max_length=32)
    target_language_id: str = Field(min_length=1, max_length=32)
    starting_choice: StartingChoice
    correction_preference: CorrectionPreference = CorrectionPreference.BALANCED
    tutor_pace: TutorPace = TutorPace.LEVEL
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    interests: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_profile(self) -> CreateProfileRequest:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        normalized: list[str] = []
        seen: set[str] = set()
        for item in self.interests:
            value = " ".join(item.split())
            if not 1 <= len(value) <= 80:
                raise ValueError("each interest must contain 1 to 80 characters")
            folded = value.casefold()
            if folded not in seen:
                normalized.append(value)
                seen.add(folded)
        if len(normalized) > 12:
            raise ValueError("interests must contain at most 12 distinct entries")
        self.interests = normalized
        return self

    def to_domain(self) -> CreateProfile:
        return CreateProfile(
            base_language_id=self.base_language_id,
            target_language_id=self.target_language_id,
            starting_choice=self.starting_choice,
            correction_preference=self.correction_preference,
            tutor_pace=self.tutor_pace,
            timezone=self.timezone,
            interests=tuple(self.interests),
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
