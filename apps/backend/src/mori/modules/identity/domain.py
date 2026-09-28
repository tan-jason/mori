"""Identity domain values with no framework or persistence dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETION_PENDING = "deletion_pending"


class LanguageProfileStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class CorrectionPreference(StrEnum):
    LIGHT = "light"
    BALANCED = "balanced"
    FREQUENT = "frequent"


class TutorPace(StrEnum):
    LEVEL = "level"
    GENTLE = "gentle"
    STEADY = "steady"
    NATURAL = "natural"


class StartingChoice(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    FLUENT = "fluent"
    UNSURE = "unsure"


class LearningMode(StrEnum):
    LEARNING = "learning"
    PRACTICE = "practice"


@dataclass(frozen=True, slots=True)
class GoogleClaims:
    subject: str
    email: str
    email_verified: bool
    display_name: str


@dataclass(frozen=True, slots=True)
class OAuthLoginAttempt:
    nonce: str
    code_verifier: str
    return_path: str


@dataclass(frozen=True, slots=True)
class ApplicationSession:
    id: UUID
    user_id: UUID
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class LanguageProfileView:
    id: UUID
    base_language_id: str
    target_language_id: str
    status: LanguageProfileStatus
    language_selection_confirmed: bool
    version: int
    starting_choice: StartingChoice
    mode: LearningMode
    provisional_level: StartingChoice | None
    learning_settings_version: int


@dataclass(frozen=True, slots=True)
class PreferencesView:
    correction_preference: CorrectionPreference
    tutor_pace: TutorPace
    captions_enabled: bool
    timezone: str
    interests: tuple[str, ...]
    version: int


@dataclass(frozen=True, slots=True)
class CurrentLearner:
    user_id: UUID
    email: str
    display_name: str
    status: UserStatus
    onboarding_complete: bool
    version: int
    language_profile: LanguageProfileView | None
    preferences: PreferencesView | None


@dataclass(frozen=True, slots=True)
class PreferenceChanges:
    correction_preference: CorrectionPreference | None = None
    tutor_pace: TutorPace | None = None
    captions_enabled: bool | None = None
    timezone: str | None = None


@dataclass(frozen=True, slots=True)
class CoursePairView:
    base_language_id: str
    target_language_id: str
    base_language_name: str
    target_language_name: str
    target_native_name: str
    available: bool


@dataclass(frozen=True, slots=True)
class CreateProfile:
    base_language_id: str
    target_language_id: str
    starting_choice: StartingChoice
    correction_preference: CorrectionPreference
    tutor_pace: TutorPace
    timezone: str
    interests: tuple[str, ...]
