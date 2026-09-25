"""Transactional intro-entitlement commands used by session orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mori.modules.access.models import EntitlementRuleModel, GrantModel
from mori.modules.access.usage_models import UsageEventModel, UsageReservationModel


@dataclass(frozen=True, slots=True)
class HeldReservation:
    id: UUID
    session_id: UUID
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class IntroGrant:
    id: UUID
    connected_limit_ms: int
    held: HeldReservation | None


class AccessCommands:
    @staticmethod
    async def claim_intro_grant(
        db: AsyncSession, *, user_id: UUID, now: datetime
    ) -> IntroGrant | None:
        grant = await db.scalar(
            select(GrantModel)
            .where(
                GrantModel.user_id == user_id,
                GrantModel.grant_type == "intro",
                GrantModel.status == "active",
                GrantModel.valid_from <= now,
                (GrantModel.valid_until.is_(None) | (GrantModel.valid_until > now)),
            )
            .with_for_update()
        )
        if grant is None:
            return None
        rule = await db.scalar(
            select(EntitlementRuleModel).where(
                EntitlementRuleModel.plan_version_id == grant.plan_version_id,
                EntitlementRuleModel.capability == "voice_session",
            )
        )
        if rule is None or rule.allowance != 1 or rule.reset_period is not None:
            return None
        consumed = await db.scalar(
            select(UsageReservationModel.id).where(
                UsageReservationModel.grant_id == grant.id,
                UsageReservationModel.state == "consumed",
            )
        )
        if consumed is not None:
            return None
        reserved = await db.scalar(
            select(UsageReservationModel).where(
                UsageReservationModel.grant_id == grant.id,
                UsageReservationModel.state == "reserved",
            )
        )
        return IntroGrant(
            id=grant.id,
            connected_limit_ms=rule.max_duration_seconds * 1000,
            held=HeldReservation(
                id=reserved.id,
                session_id=reserved.session_id,
                expires_at=reserved.expires_at,
            ) if reserved is not None else None,
        )

    @staticmethod
    async def release_expired(
        db: AsyncSession, *, reservation_id: UUID, now: datetime
    ) -> None:
        reservation = await db.get(UsageReservationModel, reservation_id)
        if reservation is None or reservation.state != "reserved" or reservation.expires_at > now:
            raise RuntimeError("reservation is not releasable")
        reservation.state = "released"
        reservation.updated_at = now
        db.add(
            UsageEventModel(
                reservation_id=reservation_id,
                kind="released",
                idempotency_key=f"reservation:{reservation_id}:expired",
                created_at=now,
            )
        )
        await db.flush()

    @staticmethod
    async def reserve_intro(
        db: AsyncSession, *, grant_id: UUID, session_id: UUID, now: datetime,
        ttl: timedelta,
    ) -> datetime:
        reservation = UsageReservationModel(
            session_id=session_id,
            grant_id=grant_id,
            state="reserved",
            expires_at=now + ttl,
            created_at=now,
            updated_at=now,
        )
        db.add(reservation)
        await db.flush()
        db.add(
            UsageEventModel(
                reservation_id=reservation.id,
                kind="reserved",
                idempotency_key=f"reservation:{reservation.id}:created",
                created_at=now,
            )
        )
        return reservation.expires_at
