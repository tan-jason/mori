"""Language profile persistence port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from mori.modules.learner_profiles.domain import (
    CreateProfile,
    LanguageProfileView,
    PlanningProfile,
    PreferenceChanges,
    PreferencesView,
)


class LearnerProfileStore(Protocol):
    async def current(
        self, user_id: UUID
    ) -> tuple[LanguageProfileView | None, PreferencesView | None]: ...

    async def replay_exists(
        self, *, user_id: UUID, key_digest: str, payload_digest: str
    ) -> bool: ...

    async def confirm(
        self,
        *,
        user_id: UUID,
        command: CreateProfile,
        key_digest: str,
        payload_digest: str,
        now: datetime,
    ) -> None: ...

    async def update_preferences(
        self,
        *,
        user_id: UUID,
        expected_version: int,
        changes: PreferenceChanges,
        now: datetime,
    ) -> None: ...

    async def for_planning(self, *, user_id: UUID, profile_id: UUID) -> PlanningProfile | None: ...
