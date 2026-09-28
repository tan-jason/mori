"""PostgreSQL adapter for the published language pair catalog."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mori.modules.curriculum.domain import CoursePairView
from mori.modules.curriculum.models import CourseCatalogModel


class SqlAlchemyCourseCatalogStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def language_pairs(self) -> tuple[CoursePairView, ...]:
        rows = (
            await self._session.scalars(
                select(CourseCatalogModel).order_by(
                    CourseCatalogModel.base_language_name,
                    CourseCatalogModel.target_language_name,
                )
            )
        ).all()
        return tuple(
            CoursePairView(
                base_language_id=row.base_language_id,
                target_language_id=row.target_language_id,
                base_language_name=row.base_language_name,
                target_language_name=row.target_language_name,
                target_native_name=row.target_native_name,
                available=self._available(row),
            )
            for row in rows
        )

    async def is_available(self, *, base_language_id: str, target_language_id: str) -> bool:
        pair = await self._session.scalar(
            select(CourseCatalogModel).where(
                CourseCatalogModel.base_language_id == base_language_id,
                CourseCatalogModel.target_language_id == target_language_id,
            )
        )
        return pair is not None and self._available(pair)

    @staticmethod
    def _available(pair: CourseCatalogModel) -> bool:
        return (
            pair.status == "published"
            and pair.active_curriculum_version is not None
            and pair.pair_policy_version is not None
            and pair.voice_policy_version is not None
            and pair.published_at is not None
        )
