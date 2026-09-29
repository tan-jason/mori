"""Authoritative session and immutable versioned plan records."""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mori.persistence.base import Base


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('created', 'reserved', 'planned', 'connecting', 'active', "
            "'reconnecting', 'ending', "
            "'analysis_pending', 'ready', 'analysis_failed', 'setup_failed')",
            name="ck_sessions_state",
        ),
        CheckConstraint("row_version > 0", name="ck_sessions_row_version"),
        CheckConstraint("connected_limit_ms > 0", name="ck_sessions_connected_limit"),
        CheckConstraint("connected_ms >= 0", name="ck_sessions_connected_ms"),
        UniqueConstraint("user_id", "creation_key_digest", name="uq_sessions_user_creation_key"),
        Index("ix_sessions_profile_created", "language_profile_id", "created_at"),
        Index("ix_sessions_state_expiry", "state", "session_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("language_profiles.id", ondelete="CASCADE"), nullable=False
    )
    creation_key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    connected_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    connected_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(String(64))
    final_turn_sequence: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionPlanModel(Base):
    __tablename__ = "session_plans"
    __table_args__ = (
        CheckConstraint("objective_count BETWEEN 1 AND 3", name="ck_session_plans_objective_count"),
        CheckConstraint(
            "schema_version = 'legacy_placeholder' OR (schema_version = 'learning_plan_v1' "
            "AND mode IN ('learning', 'practice') AND profile_version IS NOT NULL "
            "AND preference_version IS NOT NULL AND settings_version IS NOT NULL "
            "AND setup_digest IS NOT NULL AND requested_words IS NOT NULL "
            "AND curriculum_version IS NOT NULL "
            "AND base_policy_version IS NOT NULL AND pair_policy_version IS NOT NULL "
            "AND level_policy_version IS NOT NULL AND ((mode = 'learning' "
            "AND selected_level IN ('beginner', 'intermediate', 'advanced')) "
            "OR (mode = 'practice' AND selected_level IS NULL)))",
            name="ck_session_plans_v1_complete",
        ),
        CheckConstraint(
            "requested_words IS NULL OR jsonb_typeof(requested_words) = 'array'",
            name="ck_session_plans_requested_words_array",
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    curriculum_version: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="learning_plan_v1"
    )
    mode: Mapped[str | None] = mapped_column(String(16))
    snapshot_id: Mapped[UUID | None] = mapped_column()
    profile_version: Mapped[int | None] = mapped_column(Integer)
    preference_version: Mapped[int | None] = mapped_column(Integer)
    settings_version: Mapped[int | None] = mapped_column(Integer)
    selected_level: Mapped[str | None] = mapped_column(String(32))
    topic: Mapped[str | None] = mapped_column(String(160))
    requested_words: Mapped[list[str] | None] = mapped_column(JSONB)
    setup_digest: Mapped[str | None] = mapped_column(String(64))
    base_policy_version: Mapped[str | None] = mapped_column(String(64))
    pair_policy_version: Mapped[str | None] = mapped_column(String(64))
    level_policy_version: Mapped[str | None] = mapped_column(String(64))
    objective_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionPlanObjectiveModel(Base):
    __tablename__ = "session_plan_objectives"
    __table_args__ = (
        CheckConstraint("ordinal BETWEEN 1 AND 3", name="ck_session_plan_objectives_ordinal"),
        CheckConstraint(
            "kind IS NULL OR (kind = 'conversation_focus' AND curriculum_item_key IS NULL) "
            "OR (kind = 'graded' AND curriculum_item_key IS NOT NULL)",
            name="ck_plan_objective_kind",
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_plans.session_id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str | None] = mapped_column(String(32))
    curriculum_item_key: Mapped[str | None] = mapped_column(String(80))
