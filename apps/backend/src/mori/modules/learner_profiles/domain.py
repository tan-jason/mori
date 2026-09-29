"""Language profile choices and preferences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


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
class PlanningProfile:
    id: UUID
    base_language_id: str
    target_language_id: str
    mode: LearningMode
    provisional_level: StartingChoice | None
    profile_version: int
    preference_version: int
    settings_version: int


@dataclass(frozen=True, slots=True)
class PreferenceChanges:
    correction_preference: CorrectionPreference | None = None
    tutor_pace: TutorPace | None = None
    captions_enabled: bool | None = None
    timezone: str | None = None


@dataclass(frozen=True, slots=True)
class CreateProfile:
    base_language_id: str
    target_language_id: str
    starting_choice: StartingChoice
    correction_preference: CorrectionPreference
    tutor_pace: TutorPace
    timezone: str
    interests: tuple[str, ...]
