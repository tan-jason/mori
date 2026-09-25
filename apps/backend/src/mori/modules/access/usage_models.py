"""Durable voice-session reservations and append-only usage events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from mori.persistence.base import Base


class UsageReservationModel(Base):
    __tablename__ = "usage_reservations"
    __table_args__ = (
        CheckConstraint(
            "state IN ('reserved', 'consumed', 'released')",
            name="ck_usage_reservations_state",
        ),
        Index(
            "uq_usage_reservations_grant_reserved",
            "grant_id",
            unique=True,
            postgresql_where=text("state = 'reserved'"),
        ),
        Index("ix_usage_reservations_state_expiry", "state", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    grant_id: Mapped[UUID] = mapped_column(
        ForeignKey("grants.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageEventModel(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('reserved', 'consumed', 'released', 'corrected')",
            name="ck_usage_events_kind",
        ),
        Index("ix_usage_events_reservation_created", "reservation_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reservation_id: Mapped[UUID] = mapped_column(
        ForeignKey("usage_reservations.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
