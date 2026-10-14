"""Account-owned personal context, with cross-profile edits and suppression."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mori.modules.learning.learner_file import (
    LearnerFileCallActive,
    LearnerFileNotFound,
    LearnerFileVersionConflict,
)
from mori.modules.learning.models import UserInsightModel
from mori.modules.sessions.models import SessionModel
from mori.modules.user.domain import UserStatus
from mori.modules.user.persistence import SqlAlchemyUserStore
from mori.persistence.model_registry import load_models


def insight_identity(user_id: UUID, fact: str, temporal_context: str | None = None) -> str:
    # Exact normalized facts only. Separate dates remain separate facts; semantic
    # equivalence and corrections must be explicitly reviewed rather than guessed.
    canonical = " ".join(fact.casefold().split())
    temporal = " ".join((temporal_context or "").casefold().split())
    return hashlib.sha256(f"{user_id}:{canonical}:{temporal}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class UserInsightEntry:
    id: UUID
    text: str
    origin: str
    version: int
    source_session_id: UUID
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    temporal_context: str | None

    @classmethod
    def from_model(cls, model: UserInsightModel) -> UserInsightEntry:
        assert model.text is not None
        return cls(
            model.id,
            model.text,
            model.origin,
            model.version,
            model.source_session_id,
            model.created_at,
            model.updated_at,
            model.expires_at,
            model.temporal_context,
        )


@dataclass(frozen=True, slots=True)
class UserInsightPage:
    entries: tuple[UserInsightEntry, ...]
    next_cursor: tuple[datetime, UUID] | None


def _eligible(user_id: UUID, now: datetime) -> Select[tuple[UserInsightModel]]:
    return select(UserInsightModel).where(
        UserInsightModel.user_id == user_id,
        UserInsightModel.deleted_at.is_(None),
        UserInsightModel.text.is_not(None),
        or_(UserInsightModel.expires_at.is_(None), UserInsightModel.expires_at > now),
    )


async def eligible_user_insights(
    db: AsyncSession, user_id: UUID, limit: int = 5
) -> tuple[UserInsightEntry, ...]:
    if not 0 <= limit <= 10:
        raise ValueError("invalid insight context bound")
    rows = (
        await db.scalars(
            _eligible(user_id, datetime.now(UTC))
            .order_by(UserInsightModel.updated_at.desc(), UserInsightModel.id.desc())
            .limit(limit)
        )
    ).all()
    return tuple(UserInsightEntry.from_model(row) for row in rows)


class UserInsightService:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        load_models()
        self._session_maker = session_maker

    async def list(
        self, *, user_id: UUID, before: tuple[datetime, UUID] | None = None
    ) -> UserInsightPage:
        async with self._session_maker() as db:
            query = _eligible(user_id, datetime.now(UTC))
            if before is not None:
                created, entry_id = before
                query = query.where(
                    or_(
                        UserInsightModel.created_at < created,
                        and_(
                            UserInsightModel.created_at == created, UserInsightModel.id < entry_id
                        ),
                    )
                )
            rows = (
                await db.scalars(
                    query.order_by(
                        UserInsightModel.created_at.desc(), UserInsightModel.id.desc()
                    ).limit(51)
                )
            ).all()
            page = rows[:50]
            return UserInsightPage(
                tuple(UserInsightEntry.from_model(row) for row in page),
                (page[-1].created_at, page[-1].id) if len(rows) > 50 else None,
            )

    async def _lock_owner(self, db: AsyncSession, user_id: UUID) -> None:
        account = await SqlAlchemyUserStore(db).lock_for_session(user_id)
        if account is None or account.status != UserStatus.ACTIVE:
            raise LearnerFileNotFound
        active = await db.scalar(
            select(SessionModel.id)
            .where(
                SessionModel.user_id == user_id,
                SessionModel.state.in_(("connecting", "active", "reconnecting", "ending")),
            )
            .limit(1)
        )
        if active is not None:
            raise LearnerFileCallActive

    async def edit(
        self, *, user_id: UUID, entry_id: UUID, expected_version: int, text: str
    ) -> UserInsightEntry:
        normalized = " ".join(text.split())
        if not normalized or len(normalized) > 240:
            raise ValueError("invalid insight text")
        async with self._session_maker() as db, db.begin():
            await self._lock_owner(db, user_id)
            entry = await db.scalar(
                select(UserInsightModel)
                .where(
                    UserInsightModel.id == entry_id,
                    UserInsightModel.user_id == user_id,
                    UserInsightModel.deleted_at.is_(None),
                )
                .with_for_update()
            )
            if entry is None or (
                entry.expires_at is not None and entry.expires_at <= datetime.now(UTC)
            ):
                raise LearnerFileNotFound
            if entry.version != expected_version:
                raise LearnerFileVersionConflict
            # Keep the captured identity suppressed, and prevent recapture of the edit.
            if entry.edited_identity_digest is not None:
                entry.suppressed_identity_digests = [
                    *entry.suppressed_identity_digests,
                    entry.edited_identity_digest,
                ]
            entry.text = normalized
            entry.edited_identity_digest = insight_identity(
                user_id, normalized, entry.temporal_context
            )
            entry.origin = "learner_edit"
            entry.version += 1
            entry.updated_at = datetime.now(UTC)
            return UserInsightEntry.from_model(entry)

    async def delete(self, *, user_id: UUID, entry_id: UUID, expected_version: int) -> None:
        async with self._session_maker() as db, db.begin():
            await self._lock_owner(db, user_id)
            entry = await db.scalar(
                select(UserInsightModel)
                .where(
                    UserInsightModel.id == entry_id,
                    UserInsightModel.user_id == user_id,
                )
                .with_for_update()
            )
            if entry is None:
                raise LearnerFileNotFound
            if entry.deleted_at is not None:
                return
            if entry.version != expected_version:
                raise LearnerFileVersionConflict
            entry.text = None
            entry.deleted_at = datetime.now(UTC)
            entry.updated_at = entry.deleted_at
            entry.version += 1
