"""Learner-owned projections of captured learnings and insights."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mori.modules.learner_profiles.models import LanguageProfileModel
from mori.modules.learning.models import LearnerFileEntryModel
from mori.modules.sessions.models import SessionModel
from mori.modules.user.domain import UserStatus
from mori.modules.user.persistence import SqlAlchemyUserStore
from mori.persistence.model_registry import load_models


class LearnerFileNotFound(Exception):
    pass


class LearnerFileVersionConflict(Exception):
    pass


class LearnerFileCallActive(Exception):
    pass


class InvalidLearnerFileCursor(Exception):
    pass


@dataclass(frozen=True, slots=True)
class LearnerFileEntry:
    id: UUID
    kind: str
    text: str
    origin: str
    version: int
    source_session_id: UUID | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None

    @classmethod
    def from_model(cls, model: LearnerFileEntryModel) -> LearnerFileEntry:
        assert model.text is not None
        return cls(
            model.id,
            model.kind,
            model.text,
            model.origin,
            model.version,
            model.source_session_id,
            model.created_at,
            model.updated_at,
            model.expires_at,
        )


@dataclass(frozen=True, slots=True)
class LearnerFilePage:
    entries: tuple[LearnerFileEntry, ...]
    next_cursor: tuple[datetime, UUID] | None


class LearnerFileService:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        load_models()
        self._session_maker = session_maker

    async def list(
        self,
        *,
        user_id: UUID,
        profile_id: UUID,
        before: tuple[datetime, UUID] | None = None,
    ) -> LearnerFilePage:
        async with self._session_maker() as db:
            await self._owned_profile(db, user_id, profile_id)
            now = datetime.now(UTC)
            query = select(LearnerFileEntryModel).where(
                LearnerFileEntryModel.language_profile_id == profile_id,
                LearnerFileEntryModel.kind == "learning",
                LearnerFileEntryModel.deleted_at.is_(None),
                LearnerFileEntryModel.text.is_not(None),
                or_(
                    LearnerFileEntryModel.expires_at.is_(None),
                    LearnerFileEntryModel.expires_at > now,
                ),
            )
            if before is not None:
                created_at, entry_id = before
                query = query.where(
                    or_(
                        LearnerFileEntryModel.created_at < created_at,
                        and_(
                            LearnerFileEntryModel.created_at == created_at,
                            LearnerFileEntryModel.id < entry_id,
                        ),
                    )
                )
            rows = (
                await db.scalars(
                    query.order_by(
                        LearnerFileEntryModel.created_at.desc(), LearnerFileEntryModel.id.desc()
                    ).limit(51)
                )
            ).all()
            page = rows[:50]
            next_cursor = (page[-1].created_at, page[-1].id) if len(rows) > 50 else None
            return LearnerFilePage(
                tuple(LearnerFileEntry.from_model(row) for row in page), next_cursor
            )

    async def edit(
        self,
        *,
        user_id: UUID,
        profile_id: UUID,
        entry_id: UUID,
        expected_version: int,
        text: str,
    ) -> LearnerFileEntry:
        normalized = " ".join(text.split())
        if not normalized or len(normalized) > 240:
            raise ValueError("invalid learner file text")
        async with self._session_maker() as db, db.begin():
            await self._lock_owner(db, user_id, profile_id)
            entry = await db.scalar(
                select(LearnerFileEntryModel)
                .where(
                    LearnerFileEntryModel.id == entry_id,
                    LearnerFileEntryModel.language_profile_id == profile_id,
                    LearnerFileEntryModel.kind == "learning",
                    LearnerFileEntryModel.deleted_at.is_(None),
                )
                .with_for_update()
            )
            if entry is None or (
                entry.expires_at is not None and entry.expires_at <= datetime.now(UTC)
            ):
                raise LearnerFileNotFound
            if entry.version != expected_version:
                raise LearnerFileVersionConflict
            await self._require_no_active_call(db, profile_id)
            entry.text = normalized
            await self._suppress_evidence(db, entry)
            entry.origin = "learner_edit"
            entry.version += 1
            entry.updated_at = datetime.now(UTC)
            return LearnerFileEntry.from_model(entry)

    async def delete(
        self,
        *,
        user_id: UUID,
        profile_id: UUID,
        entry_id: UUID,
        expected_version: int,
    ) -> None:
        async with self._session_maker() as db, db.begin():
            await self._lock_owner(db, user_id, profile_id)
            entry = await db.scalar(
                select(LearnerFileEntryModel)
                .where(
                    LearnerFileEntryModel.id == entry_id,
                    LearnerFileEntryModel.language_profile_id == profile_id,
                    LearnerFileEntryModel.kind == "learning",
                )
                .with_for_update()
            )
            if entry is None:
                raise LearnerFileNotFound
            if entry.deleted_at is not None:
                return
            if entry.version != expected_version:
                raise LearnerFileVersionConflict
            await self._require_no_active_call(db, profile_id)
            await self._suppress_evidence(db, entry)
            entry.text = None
            entry.origin = "learner_edit"
            entry.deleted_at = datetime.now(UTC)
            entry.updated_at = entry.deleted_at
            entry.version += 1

    @staticmethod
    async def _suppress_evidence(db: AsyncSession, entry: LearnerFileEntryModel) -> None:
        from mori.modules.learning.models import LanguageItemModel, ProfileLearningStateModel

        now = datetime.now(UTC)
        if entry.language_item_id is not None:
            item = await db.get(LanguageItemModel, entry.language_item_id)
            if item is not None:
                item.suppressed_at = now
        state = await db.get(ProfileLearningStateModel, entry.language_profile_id)
        if state is None:
            state = ProfileLearningStateModel(
                language_profile_id=entry.language_profile_id, history_revision=0, updated_at=now
            )
            db.add(state)
        state.history_revision += 1
        state.updated_at = now

    async def _owned_profile(self, db: AsyncSession, user_id: UUID, profile_id: UUID) -> None:
        owner = await db.scalar(
            select(LanguageProfileModel.id).where(
                LanguageProfileModel.id == profile_id,
                LanguageProfileModel.user_id == user_id,
            )
        )
        if owner is None:
            raise LearnerFileNotFound

    async def _lock_owner(self, db: AsyncSession, user_id: UUID, profile_id: UUID) -> None:
        account = await SqlAlchemyUserStore(db).lock_for_session(user_id)
        if account is None or account.status != UserStatus.ACTIVE:
            raise LearnerFileNotFound
        await self._owned_profile(db, user_id, profile_id)

    async def _require_no_active_call(self, db: AsyncSession, profile_id: UUID) -> None:
        active = await db.scalar(
            select(SessionModel.id)
            .where(
                SessionModel.language_profile_id == profile_id,
                SessionModel.state.in_(("connecting", "active", "reconnecting", "ending")),
            )
            .limit(1)
        )
        if active is not None:
            raise LearnerFileCallActive
