"""Account persistence port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from mori.modules.accounts.domain import AccountView


class AccountStore(Protocol):
    async def create_or_update(
        self, *, user_id: UUID | None, email: str, display_name: str, now: datetime
    ) -> UUID: ...

    async def active(self, user_id: UUID, *, lock: bool = False) -> AccountView: ...

    async def lock_for_session(self, user_id: UUID) -> AccountView | None: ...

    async def complete_onboarding(self, user_id: UUID, *, now: datetime) -> None: ...
