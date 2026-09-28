"""Language profile, preference, and onboarding persistence entities."""

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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mori.persistence.base import Base


class LanguageProfileModel(Base):
    __tablename__ = "language_profiles"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_language_profiles_status"),
        CheckConstraint("version > 0", name="ck_language_profiles_version"),
        UniqueConstraint(
            "user_id",
            "base_language_id",
            "target_language_id",
            name="uq_language_profiles_user_language_pair",
        ),
        Index(
            "uq_language_profiles_one_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    base_language_id: Mapped[str] = mapped_column(String(32), nullable=False)
    target_language_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
    language_selection_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class LearnerPreferenceModel(Base):
    __tablename__ = "learner_preferences"
    __table_args__ = (
        CheckConstraint(
            "correction_preference IN ('light', 'balanced', 'frequent')",
            name="ck_learner_preferences_correction",
        ),
        CheckConstraint(
            "tutor_pace IN ('level', 'gentle', 'steady', 'natural')",
            name="ck_learner_preferences_tutor_pace",
        ),
        CheckConstraint("version > 0", name="ck_learner_preferences_version"),
        CheckConstraint(
            "jsonb_typeof(interests) = 'array'",
            name="ck_learner_preferences_interests_array",
        ),
    )

    language_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("language_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    correction_preference: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="balanced"
    )
    tutor_pace: Mapped[str] = mapped_column(String(32), nullable=False, server_default="level")
    captions_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="America/New_York"
    )
    interests: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class ProfileLearningSettingsModel(Base):
    __tablename__ = "profile_learning_settings"
    __table_args__ = (
        CheckConstraint(
            "starting_choice IN ('beginner', 'intermediate', 'advanced', 'fluent', 'unsure')",
            name="ck_profile_learning_settings_choice",
        ),
        CheckConstraint(
            "(mode = 'practice' AND starting_choice = 'fluent' AND provisional_level IS NULL) "
            "OR (mode = 'learning' AND starting_choice != 'fluent' "
            "AND provisional_level IN ('beginner', 'intermediate', 'advanced'))",
            name="ck_profile_learning_settings_mode",
        ),
        CheckConstraint("version > 0", name="ck_profile_learning_settings_version"),
    )

    language_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("language_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    starting_choice: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    provisional_level: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OnboardingCommandModel(Base):
    __tablename__ = "onboarding_commands"
    __table_args__ = (
        UniqueConstraint("user_id", "key_digest", name="uq_onboarding_commands_user_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    language_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("language_profiles.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
