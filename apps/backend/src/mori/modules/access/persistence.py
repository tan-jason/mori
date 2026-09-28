"""PostgreSQL adapter for grant issuance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mori.modules.access.constants import INTRO_PLAN_VERSION_ID
from mori.modules.access.models import GrantModel


class SqlAlchemyAccessStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_intro_grant(self, *, user_id: UUID, now: datetime) -> None:
        grant = await self._session.scalar(
            select(GrantModel).where(
                GrantModel.user_id == user_id,
                GrantModel.grant_type == "intro",
            )
        )
        if grant is None:
            self._session.add(
                GrantModel(
                    user_id=user_id,
                    plan_version_id=INTRO_PLAN_VERSION_ID,
                    grant_type="intro",
                    status="active",
                    valid_from=now,
                    created_at=now,
                )
            )
            await self._session.flush()
