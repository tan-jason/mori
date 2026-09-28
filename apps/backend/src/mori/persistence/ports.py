"""Shared transaction boundary for cooperating modules."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from mori.modules.accounts.ports import AccountStore
from mori.modules.curriculum.ports import CourseCatalogStore
from mori.modules.identity.ports import IdentityStore
from mori.modules.learner_profiles.ports import LearnerProfileStore


class AccessStore(Protocol):
    async def ensure_intro_grant(self, *, user_id: UUID, now: datetime) -> None: ...


class UnitOfWork(Protocol):
    @property
    def identity(self) -> IdentityStore: ...

    @property
    def accounts(self) -> AccountStore: ...

    @property
    def profiles(self) -> LearnerProfileStore: ...

    @property
    def curriculum(self) -> CourseCatalogStore: ...

    @property
    def access(self) -> AccessStore: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...
