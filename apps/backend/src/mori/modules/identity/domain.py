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


@dataclass(frozen=True, slots=True)
class PreferencesView:
    correction_preference: CorrectionPreference
    tutor_pace: TutorPace
    captions_enabled: bool
    timezone: str
    version: int


@dataclass(frozen=True, slots=True)
class CurrentLearner:
    user_id: UUID
    email: str
    display_name: str
    status: UserStatus
    onboarding_complete: bool
    language_profile: LanguageProfileView
    preferences: PreferencesView


@dataclass(frozen=True, slots=True)
class PreferenceChanges:
    correction_preference: CorrectionPreference | None = None
    tutor_pace: TutorPace | None = None
    captions_enabled: bool | None = None
    timezone: str | None = None
