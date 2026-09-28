"""PostgreSQL adapter for application accounts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mori.modules.accounts.domain import AccountView, UserStatus
from mori.modules.accounts.errors import AccountUnavailable
from mori.modules.accounts.models import UserModel


class SqlAlchemyAccountStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_or_update(
        self, *, user_id: UUID | None, email: str, display_name: str, now: datetime
    ) -> UUID:
        if user_id is None:
            user = UserModel(
                status=UserStatus.ACTIVE.value,
                email=email,
                display_name=display_name,
                created_at=now,
                updated_at=now,
            )
            self._session.add(user)
        else:
            existing = await self._session.get(UserModel, user_id)
            if existing is None:
                raise RuntimeError("external identity has no account")
            user = existing
            if user.status != UserStatus.ACTIVE.value:
                raise AccountUnavailable
            user.email = email
            user.display_name = display_name
            user.updated_at = now
        await self._session.flush()
        return user.id

    async def active(self, user_id: UUID, *, lock: bool = False) -> AccountView:
        statement = select(UserModel).where(UserModel.id == user_id)
        if lock:
            statement = statement.with_for_update()
        user = await self._session.scalar(statement)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise AccountUnavailable
        return self._view(user)

    async def lock_for_session(self, user_id: UUID) -> AccountView | None:
        user = await self._session.scalar(
            select(UserModel).where(UserModel.id == user_id).with_for_update()
        )
        return self._view(user) if user is not None else None

    async def complete_onboarding(self, user_id: UUID, *, now: datetime) -> None:
        user = await self._session.get(UserModel, user_id)
        if user is None:
            raise RuntimeError("onboarding account does not exist")
        if user.onboarding_completed_at is None:
            user.onboarding_completed_at = now
        user.version += 1
        user.updated_at = now
        await self._session.flush()

    @staticmethod
    def _view(user: UserModel) -> AccountView:
        return AccountView(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=UserStatus(user.status),
            version=user.version,
            onboarding_completed_at=user.onboarding_completed_at,
        )
