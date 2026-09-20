"""Identity persistence entities owned by the identity module."""

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
from sqlalchemy.orm import Mapped, mapped_column

from mori.persistence.base import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'deletion_pending')",
            name="ck_users_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class ExternalIdentityModel(Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        CheckConstraint("provider = 'google'", name="ck_external_identities_provider"),
        UniqueConstraint("provider", "subject", name="uq_external_identities_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_external_identities_user_provider"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, server_default="google")
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    last_authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class OAuthLoginAttemptModel(Base):
    __tablename__ = "oauth_login_attempts"
    __table_args__ = (Index("ix_oauth_login_attempts_expires_at", "expires_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    state_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    return_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSessionModel(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_expires", "user_id", "expires_at"),
        Index(
            "ix_auth_sessions_active_expiry",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LanguageProfileModel(Base):
    __tablename__ = "language_profiles"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_language_profiles_status"),
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
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class UserConsentModel(Base):
    __tablename__ = "user_consents"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('granted', 'declined', 'revoked')",
            name="ck_user_consents_decision",
        ),
        Index("ix_user_consents_user_policy_recorded", "user_id", "policy_kind", "recorded_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    policy_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
