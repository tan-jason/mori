"""Durable analysis records and exact-turn provenance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from mori.persistence.base import Base


class AnalysisRunModel(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index(
            "uq_analysis_run_pending_session",
            "session_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        CheckConstraint("status IN ('pending', 'ready', 'failed')", name="ck_analysis_run_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    extractor_model: Mapped[str] = mapped_column(String(128), nullable=False)
    curriculum_version: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    final_turn_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecapModel(Base):
    __tablename__ = "recaps"
    __table_args__ = (Index("ix_recaps_session_created", "session_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnalysisObservationModel(Base):
    __tablename__ = "analysis_observations"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "ordinal", name="uq_analysis_observation_ordinal"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_analysis_observation_confidence"
        ),
        CheckConstraint(
            "review_status IN ('legacy', 'supported')",
            name="ck_analysis_observation_review_status",
        ),
        CheckConstraint(
            "review_status <> 'supported' OR "
            "(curriculum_item_key IS NOT NULL AND review_reason IS NOT NULL "
            "AND length(trim(review_reason)) > 0)",
            name="ck_analysis_observation_review_context",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(String(240), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    curriculum_item_key: Mapped[str | None] = mapped_column(String(128))
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="legacy")
    review_reason: Mapped[str | None] = mapped_column(String(240))


class AnalysisObservationTurnModel(Base):
    __tablename__ = "analysis_observation_turns"
    __table_args__ = (
        Index("ix_analysis_evidence_learner_turn", "turn_id"),
        Index("ix_analysis_evidence_opportunity", "opportunity_turn_id"),
        CheckConstraint(
            "(learner_quote IS NULL AND learner_quote_start IS NULL "
            "AND learner_quote_end IS NULL AND assistance IS NULL "
            "AND opportunity_turn_id IS NULL) OR "
            "(learner_quote IS NOT NULL AND learner_quote_start IS NOT NULL "
            "AND learner_quote_end IS NOT NULL AND learner_quote_start >= 0 "
            "AND learner_quote_end > learner_quote_start "
            "AND learner_quote_end - learner_quote_start = char_length(learner_quote) "
            "AND assistance IS NOT NULL "
            "AND assistance IN ('independent', 'cued', 'modelled', 'unknown'))",
            name="ck_analysis_evidence_learner_span",
        ),
        CheckConstraint(
            "(opportunity_turn_id IS NULL AND opportunity_quote IS NULL "
            "AND opportunity_quote_start IS NULL AND opportunity_quote_end IS NULL) OR "
            "(opportunity_turn_id IS NOT NULL AND opportunity_quote IS NOT NULL "
            "AND opportunity_quote_start IS NOT NULL AND opportunity_quote_end IS NOT NULL "
            "AND opportunity_quote_start >= 0 AND opportunity_quote_end > opportunity_quote_start "
            "AND opportunity_quote_end - opportunity_quote_start = char_length(opportunity_quote))",
            name="ck_analysis_evidence_opportunity_span",
        ),
    )

    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_observations.id", ondelete="CASCADE"), primary_key=True
    )
    turn_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_turns.id", ondelete="CASCADE"), primary_key=True
    )
    learner_quote: Mapped[str | None] = mapped_column(String(200))
    learner_quote_start: Mapped[int | None] = mapped_column(Integer)
    learner_quote_end: Mapped[int | None] = mapped_column(Integer)
    opportunity_turn_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("session_turns.id", ondelete="CASCADE")
    )
    opportunity_quote: Mapped[str | None] = mapped_column(String(200))
    opportunity_quote_start: Mapped[int | None] = mapped_column(Integer)
    opportunity_quote_end: Mapped[int | None] = mapped_column(Integer)
    assistance: Mapped[str | None] = mapped_column(String(16))


class AnalysisCorrectionModel(Base):
    __tablename__ = "analysis_corrections"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "ordinal", name="uq_analysis_correction_ordinal"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    learner_turn_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_turns.id", ondelete="CASCADE"), nullable=False
    )
    suggestion: Mapped[str] = mapped_column(String(240), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class LearnerFileEntryModel(Base):
    __tablename__ = "learner_file_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('learning', 'insight')", name="ck_learner_file_kind"),
        CheckConstraint("origin IN ('capture', 'learner_edit')", name="ck_learner_file_origin"),
        CheckConstraint("version > 0", name="ck_learner_file_version"),
        CheckConstraint(
            "text IS NOT NULL OR deleted_at IS NOT NULL", name="ck_learner_file_deleted_text"
        ),
        CheckConstraint(
            "kind <> 'insight' OR (expires_at IS NOT NULL AND insight_topic IS NOT NULL)",
            name="ck_learner_file_insight_expiry",
        ),
        CheckConstraint(
            "kind <> 'learning' OR (expires_at IS NULL AND insight_topic IS NULL)",
            name="ck_learner_file_learning_shape",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_learner_file_confidence",
        ),
        Index(
            "ix_learner_file_profile_active",
            "language_profile_id",
            "deleted_at",
            "created_at",
            "id",
        ),
        Index("ix_learner_file_profile_fact", "language_profile_id", "fact_digest"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    language_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("language_profiles.id", ondelete="CASCADE"), nullable=False
    )
    source_observation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("analysis_observations.id", ondelete="SET NULL"), unique=True
    )
    source_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    source_turn_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("session_turns.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    insight_topic: Mapped[str | None] = mapped_column(String(16))
    fact_digest: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str | None] = mapped_column(String(240))
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
