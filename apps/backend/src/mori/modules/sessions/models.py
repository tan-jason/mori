"""Authoritative session and immutable versioned plan records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
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


class SessionCallAttemptModel(Base):
    __tablename__ = "session_call_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_session_call_attempt_number"),
        CheckConstraint(
            "state IN ('bootstrap_pending', 'awaiting_client', 'active', 'ending', "
            "'ended', 'provider_failed', 'ambiguous', 'cleanup_pending')",
            name="ck_session_call_attempt_state",
        ),
        UniqueConstraint("session_id", "attempt_number", name="uq_session_call_attempt_number"),
        Index(
            "uq_session_call_attempt_open",
            "session_id",
            unique=True,
            postgresql_where=text(
                "state IN ('bootstrap_pending', 'awaiting_client', 'active', 'ending', "
                "'ambiguous', 'cleanup_pending')"
            ),
        ),
        Index("ix_session_call_attempt_recovery", "state", "pending_expires_at"),
        Index("ix_session_call_attempt_lease", "state", "lease_until"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_call_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    pending_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hard_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_ack_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sideband_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transcript_gap: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    lease_owner: Mapped[UUID | None] = mapped_column()
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionTurnModel(Base):
    __tablename__ = "session_turns"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "provider_item_id", "role", name="uq_session_turn_item_role"
        ),
        UniqueConstraint("session_id", "sequence", name="uq_session_turn_sequence"),
        CheckConstraint("sequence > 0", name="ck_session_turn_sequence"),
        CheckConstraint("role IN ('learner', 'tutor')", name="ck_session_turn_role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    provider_item_id: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionPromptBuildModel(Base):
    __tablename__ = "session_prompt_builds"

    call_attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_call_attempts.id", ondelete="CASCADE"), primary_key=True
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_plans.session_id", ondelete="CASCADE"), nullable=False
    )
    base_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    pair_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    level_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    voice_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(128), nullable=False)
    voice_alias: Mapped[str] = mapped_column(String(128), nullable=False)
    instructions_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
