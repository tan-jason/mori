"""Account values and the composed current learner view."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from mori.modules.learner_profiles.domain import LanguageProfileView, PreferencesView


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETION_PENDING = "deletion_pending"


@dataclass(frozen=True, slots=True)
class AccountView:
    id: UUID
    email: str
    display_name: str
    status: UserStatus
    version: int
    onboarding_completed_at: datetime | None


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
