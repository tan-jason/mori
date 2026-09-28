"""Add explicit, idempotent language-profile onboarding.

Revision ID: 20260926_0003
Revises: 20260924_0002
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260926_0003"
down_revision: str | None = "20260924_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.create_check_constraint("ck_users_version", "users", "version > 0")
    op.add_column(
        "language_profiles",
        sa.Column("language_selection_confirmed_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "language_profiles", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.create_check_constraint("ck_language_profiles_version", "language_profiles", "version > 0")
    op.add_column(
        "learner_preferences",
        sa.Column("interests", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.create_check_constraint(
        "ck_learner_preferences_interests_array",
        "learner_preferences",
        "jsonb_typeof(interests) = 'array'",
    )

    op.create_table(
        "profile_learning_settings",
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("starting_choice", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("provisional_level", sa.String(32)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "starting_choice IN ('beginner', 'intermediate', 'advanced', 'fluent', 'unsure')",
            name="ck_profile_learning_settings_choice",
        ),
        sa.CheckConstraint(
            "(mode = 'practice' AND starting_choice = 'fluent' AND provisional_level IS NULL) "
            "OR (mode = 'learning' AND starting_choice != 'fluent' "
            "AND provisional_level IN ('beginner', 'intermediate', 'advanced'))",
            name="ck_profile_learning_settings_mode",
        ),
        sa.CheckConstraint("version > 0", name="ck_profile_learning_settings_version"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("language_profile_id"),
    )

    catalog = op.create_table(
        "course_catalog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("base_language_id", sa.String(32), nullable=False),
        sa.Column("target_language_id", sa.String(32), nullable=False),
        sa.Column("base_language_name", sa.String(80), nullable=False),
        sa.Column("target_language_name", sa.String(80), nullable=False),
        sa.Column("target_native_name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("active_curriculum_version", sa.String(64)),
        sa.Column("pair_policy_version", sa.String(64)),
        sa.Column("voice_policy_version", sa.String(64)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="ck_course_catalog_status"
        ),
        sa.CheckConstraint(
            "status != 'published' OR "
            "(active_curriculum_version IS NOT NULL AND pair_policy_version IS NOT NULL "
            "AND voice_policy_version IS NOT NULL AND published_at IS NOT NULL)",
            name="ck_course_catalog_published_bundle",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "base_language_id", "target_language_id", name="uq_course_catalog_pair"
        ),
    )
    now = datetime(2026, 9, 26, tzinfo=UTC)
    targets = [
        ("mandarin", "Mandarin", "中文"),
        ("spanish", "Spanish", "Español"),
        ("french", "French", "Français"),
        ("portuguese", "Portuguese", "Português"),
        ("japanese", "Japanese", "日本語"),
        ("korean", "Korean", "한국어"),
        ("vietnamese", "Vietnamese", "Tiếng Việt"),
    ]
    op.bulk_insert(
        catalog,
        [
            {
                "id": UUID(int=index + 1),
                "base_language_id": "english",
                "target_language_id": target_id,
                "base_language_name": "English",
                "target_language_name": name,
                "target_native_name": native_name,
                "status": "published" if index == 0 else "draft",
                "active_curriculum_version": "m2-placeholder-v1" if index == 0 else None,
                "pair_policy_version": "m2-placeholder-v1" if index == 0 else None,
                "voice_policy_version": "m2-placeholder-v1" if index == 0 else None,
                "published_at": now if index == 0 else None,
            }
            for index, (target_id, name, native_name) in enumerate(targets)
        ],
    )

    op.create_table(
        "onboarding_commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key_digest", sa.String(64), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key_digest", name="uq_onboarding_commands_user_key"),
    )


def downgrade() -> None:
    op.drop_table("onboarding_commands")
    op.drop_table("course_catalog")
    op.drop_table("profile_learning_settings")
    op.drop_constraint("ck_learner_preferences_interests_array", "learner_preferences")
    op.drop_column("learner_preferences", "interests")
    op.drop_constraint("ck_language_profiles_version", "language_profiles")
    op.drop_column("language_profiles", "version")
    op.drop_column("language_profiles", "language_selection_confirmed_at")
    op.drop_constraint("ck_users_version", "users")
    op.drop_column("users", "version")
