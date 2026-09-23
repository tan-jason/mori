"""Versioned plans, entitlement rules, and grants owned by access."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from mori.persistence.base import Base


class PlanVersionModel(Base):
    __tablename__ = "plan_versions"
    __table_args__ = (
        CheckConstraint("status IN ('published', 'retired')", name="ck_plan_versions_status"),
        CheckConstraint("version > 0", name="ck_plan_versions_version"),
        UniqueConstraint("plan_code", "version", name="uq_plan_versions_code_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EntitlementRuleModel(Base):
    __tablename__ = "entitlement_rules"
    __table_args__ = (
        CheckConstraint("allowance > 0", name="ck_entitlement_rules_allowance"),
        CheckConstraint(
            "max_duration_seconds > 0",
            name="ck_entitlement_rules_max_duration",
        ),
        CheckConstraint(
            "reset_period IS NULL OR reset_period IN ('weekly')",
            name="ck_entitlement_rules_reset_period",
        ),
        UniqueConstraint(
            "plan_version_id",
            "capability",
            name="uq_entitlement_rules_plan_capability",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("plan_versions.id", ondelete="RESTRICT"), nullable=False
    )
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    allowance: Mapped[int] = mapped_column(Integer, nullable=False)
    max_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    reset_period: Mapped[str | None] = mapped_column(String(32))
    reset_timezone: Mapped[str | None] = mapped_column(String(64))


class GrantModel(Base):
    __tablename__ = "grants"
    __table_args__ = (
        CheckConstraint(
            "grant_type IN ('intro', 'subscription', 'promotion')",
            name="ck_grants_type",
        ),
        CheckConstraint(
            "status IN ('active', 'consumed', 'expired', 'revoked')",
            name="ck_grants_status",
        ),
        Index(
            "uq_grants_one_intro_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("grant_type = 'intro'"),
        ),
        Index("ix_grants_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("plan_versions.id", ondelete="RESTRICT"), nullable=False
    )
    grant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
