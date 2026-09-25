"""Idempotent, transactional first-session planning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mori.modules.access.application import AccessCommands
from mori.modules.access.usage_models import UsageReservationModel
from mori.modules.identity.models import LanguageProfileModel, UserModel
from mori.modules.sessions.errors import (
    IdempotencyConflict,
    InvalidIdempotencyKey,
    SessionNotFound,
    VoiceEntitlementUnavailable,
)
from mori.modules.sessions.models import SessionModel, SessionPlanModel, SessionPlanObjectiveModel

_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_-]{7,127}\Z")
_RESERVATION_TTL = timedelta(minutes=10)
_OBJECTIVE = "Introduce yourself and describe one thing from your week."


@dataclass(frozen=True, slots=True)
class SessionView:
    id: UUID
    state: str
    row_version: int
    connected_limit_ms: int
    connected_ms: int
    reservation_expires_at: datetime
    objective: str
    created_at: datetime


class SessionService:
    def __init__(
        self,
        *,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_maker = session_maker

    async def create(
        self, *, user_id: UUID, language_profile_id: UUID, idempotency_key: str
    ) -> tuple[SessionView, bool]:
        if not _KEY_PATTERN.fullmatch(idempotency_key):
            raise InvalidIdempotencyKey
        digest = sha256(idempotency_key.encode("ascii")).hexdigest()
        async with self._session_maker() as db, db.begin():
            # The account lock serializes duplicate keys and competing attempts
            # to reserve the same final grant, including across API processes.
            user = await db.scalar(
                select(UserModel).where(UserModel.id == user_id).with_for_update()
            )
            if user is None or user.status != "active":
                raise VoiceEntitlementUnavailable
            now = datetime.now(UTC)

            existing = await db.scalar(
                select(SessionModel).where(
                    SessionModel.user_id == user_id,
                    SessionModel.creation_key_digest == digest,
                )
            )
            if existing is not None:
                if existing.language_profile_id != language_profile_id:
                    raise IdempotencyConflict
                return await self._view(db, existing), False

            profile = await db.scalar(
                select(LanguageProfileModel).where(
                    LanguageProfileModel.id == language_profile_id,
                    LanguageProfileModel.user_id == user_id,
                    LanguageProfileModel.status == "active",
                )
            )
            if profile is None:
                raise VoiceEntitlementUnavailable

            grant = await AccessCommands.claim_intro_grant(db, user_id=user_id, now=now)
            if grant is None:
                raise VoiceEntitlementUnavailable

            held = grant.held
            if held is not None:
                previous = await db.get(SessionModel, held.session_id)
                if held.expires_at > now or previous is None:
                    raise VoiceEntitlementUnavailable
                if previous.state != "planned":
                    raise VoiceEntitlementUnavailable
                await self._transition(
                    db, previous.id, expected="planned", version=previous.row_version,
                    target="setup_failed", now=now,
                )
                await AccessCommands.release_expired(db, reservation_id=held.id, now=now)

            session = SessionModel(
                user_id=user_id,
                language_profile_id=language_profile_id,
                creation_key_digest=digest,
                state="created",
                row_version=1,
                connected_limit_ms=grant.connected_limit_ms,
                connected_ms=0,
                created_at=now,
                updated_at=now,
            )
            db.add(session)
            await db.flush()
            reservation_expires_at = await AccessCommands.reserve_intro(
                db, grant_id=grant.id, session_id=session.id, now=now, ttl=_RESERVATION_TTL
            )
            await self._transition(
                db, session.id, expected="created", version=1, target="reserved", now=now
            )
            db.add(
                SessionPlanModel(
                    session_id=session.id,
                    curriculum_version="m2-placeholder-v1",
                    selection_rule_version="m2-placeholder-v1",
                    prompt_version="m2-placeholder-v1",
                    objective_count=1,
                    created_at=now,
                )
            )
            db.add(SessionPlanObjectiveModel(session_id=session.id, ordinal=1, text=_OBJECTIVE))
            await self._transition(
                db, session.id, expected="reserved", version=2, target="planned", now=now
            )
            return SessionView(
                id=session.id,
                state="planned",
                row_version=3,
                connected_limit_ms=grant.connected_limit_ms,
                connected_ms=0,
                reservation_expires_at=reservation_expires_at,
                objective=_OBJECTIVE,
                created_at=now,
            ), True

    async def get(self, *, user_id: UUID, session_id: UUID) -> SessionView:
        async with self._session_maker() as db:
            session = await db.scalar(
                select(SessionModel).where(
                    SessionModel.id == session_id, SessionModel.user_id == user_id
                )
            )
            if session is None:
                raise SessionNotFound
            return await self._view(db, session)

    async def _view(self, db: AsyncSession, session: SessionModel) -> SessionView:
        plan = await db.get(SessionPlanModel, session.id)
        objective = await db.get(SessionPlanObjectiveModel, (session.id, 1))
        reservation = await db.scalar(
            select(UsageReservationModel).where(UsageReservationModel.session_id == session.id)
        )
        if plan is None or objective is None or reservation is None:
            raise RuntimeError("planned session is missing its plan, objective, or reservation")
        return SessionView(
            id=session.id,
            state=session.state,
            row_version=session.row_version,
            connected_limit_ms=session.connected_limit_ms,
            connected_ms=session.connected_ms,
            reservation_expires_at=reservation.expires_at,
            objective=objective.text,
            created_at=session.created_at,
        )

    @staticmethod
    async def _transition(
        db: AsyncSession, session_id: UUID, *, expected: str, version: int, target: str,
        now: datetime,
    ) -> None:
        result = await db.execute(
            update(SessionModel)
            .where(
                SessionModel.id == session_id,
                SessionModel.state == expected,
                SessionModel.row_version == version,
            )
            .values(state=target, row_version=version + 1, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise RuntimeError("session transition lost its expected state")
