"""Create identity and introductory access foundations.

Revision ID: 20260903_0001
Revises:
Create Date: 2026-09-03
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INTRO_PLAN_VERSION_ID = UUID("8a120af0-8d81-4b9d-bf8a-a4206f3bad0e")
_INTRO_ENTITLEMENT_RULE_ID = UUID("6a6e1b0d-b750-4ccb-9185-a5b06879df2f")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'deletion_pending')", name="ck_users_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="google", nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("provider = 'google'", name="ck_external_identities_provider"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "subject", name="uq_external_identities_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_external_identities_user_provider"),
    )

    op.create_table(
        "oauth_login_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state_digest", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("return_path", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_digest"),
    )
    op.create_index("ix_oauth_login_attempts_expires_at", "oauth_login_attempts", ["expires_at"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(
        "ix_auth_sessions_active_expiry",
        "auth_sessions",
        ["expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index("ix_auth_sessions_user_expires", "auth_sessions", ["user_id", "expires_at"])

    op.create_table(
        "language_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("base_language_id", sa.String(length=32), nullable=False),
        sa.Column("target_language_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_language_profiles_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "base_language_id",
            "target_language_id",
            name="uq_language_profiles_user_language_pair",
        ),
    )
    op.create_index(
        "uq_language_profiles_one_active",
        "language_profiles",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "learner_preferences",
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column(
            "correction_preference", sa.String(length=32), server_default="balanced", nullable=False
        ),
        sa.Column("tutor_pace", sa.String(length=32), server_default="level", nullable=False),
        sa.Column("captions_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "timezone", sa.String(length=64), server_default="America/New_York", nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "correction_preference IN ('light', 'balanced', 'frequent')",
            name="ck_learner_preferences_correction",
        ),
        sa.CheckConstraint(
            "tutor_pace IN ('level', 'gentle', 'steady', 'natural')",
            name="ck_learner_preferences_tutor_pace",
        ),
        sa.CheckConstraint("version > 0", name="ck_learner_preferences_version"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("language_profile_id"),
    )

    op.create_table(
        "user_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("policy_kind", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('granted', 'declined', 'revoked')", name="ck_user_consents_decision"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_consents_user_policy_recorded",
        "user_consents",
        ["user_id", "policy_kind", "recorded_at"],
    )

    plan_versions = op.create_table(
        "plan_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('published', 'retired')", name="ck_plan_versions_status"),
        sa.CheckConstraint("version > 0", name="ck_plan_versions_version"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_code", "version", name="uq_plan_versions_code_version"),
    )

    entitlement_rules = op.create_table(
        "entitlement_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_version_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("allowance", sa.Integer(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("reset_period", sa.String(length=32), nullable=True),
        sa.Column("reset_timezone", sa.String(length=64), nullable=True),
        sa.CheckConstraint("allowance > 0", name="ck_entitlement_rules_allowance"),
        sa.CheckConstraint("max_duration_seconds > 0", name="ck_entitlement_rules_max_duration"),
        sa.CheckConstraint(
            "reset_period IS NULL OR reset_period IN ('weekly')",
            name="ck_entitlement_rules_reset_period",
        ),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plan_version_id", "capability", name="uq_entitlement_rules_plan_capability"
        ),
    )

    op.create_table(
        "grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version_id", sa.Uuid(), nullable=False),
        sa.Column("grant_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "grant_type IN ('intro', 'subscription', 'promotion')", name="ck_grants_type"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'consumed', 'expired', 'revoked')", name="ck_grants_status"
        ),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grants_user_status", "grants", ["user_id", "status"])
    op.create_index(
        "uq_grants_one_intro_per_user",
        "grants",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("grant_type = 'intro'"),
    )

    published_at = datetime(2026, 9, 3, tzinfo=UTC)
    op.bulk_insert(
        plan_versions,
        [
            {
                "id": _INTRO_PLAN_VERSION_ID,
                "plan_code": "intro",
                "version": 1,
                "display_name": "Introductory access",
                "status": "published",
                "published_at": published_at,
            }
        ],
    )
    op.bulk_insert(
        entitlement_rules,
        [
            {
                "id": _INTRO_ENTITLEMENT_RULE_ID,
                "plan_version_id": _INTRO_PLAN_VERSION_ID,
                "capability": "voice_session",
                "allowance": 1,
                "max_duration_seconds": 1200,
                "reset_period": None,
                "reset_timezone": None,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_grants_one_intro_per_user", table_name="grants")
    op.drop_index("ix_grants_user_status", table_name="grants")
    op.drop_table("grants")
    op.drop_table("entitlement_rules")
    op.drop_table("plan_versions")
    op.drop_index("ix_user_consents_user_policy_recorded", table_name="user_consents")
    op.drop_table("user_consents")
    op.drop_table("learner_preferences")
    op.drop_index("uq_language_profiles_one_active", table_name="language_profiles")
    op.drop_table("language_profiles")
    op.drop_index("ix_auth_sessions_user_expires", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_active_expiry", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_oauth_login_attempts_expires_at", table_name="oauth_login_attempts")
    op.drop_table("oauth_login_attempts")
    op.drop_table("external_identities")
    op.drop_table("users")
