"""Add editable learner-file projections of captured analysis.

Revision ID: 20261007_0012
Revises: 20261006_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0012"
down_revision: str | None = "20261006_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learner_file_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "language_profile_id",
            sa.Uuid(),
            sa.ForeignKey("language_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_observation_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_observations.id", ondelete="SET NULL"),
            unique=True,
        ),
        sa.Column(
            "source_session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_turn_id",
            sa.Uuid(),
            sa.ForeignKey("session_turns.id", ondelete="SET NULL"),
            unique=True,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("insight_topic", sa.String(16)),
        sa.Column("text", sa.String(240)),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('learning', 'insight')", name="ck_learner_file_kind"),
        sa.CheckConstraint("origin IN ('capture', 'learner_edit')", name="ck_learner_file_origin"),
        sa.CheckConstraint("version > 0", name="ck_learner_file_version"),
        sa.CheckConstraint(
            "text IS NOT NULL OR deleted_at IS NOT NULL", name="ck_learner_file_deleted_text"
        ),
        sa.CheckConstraint(
            "kind <> 'insight' OR (expires_at IS NOT NULL AND insight_topic IS NOT NULL)",
            name="ck_learner_file_insight_expiry",
        ),
        sa.CheckConstraint(
            "kind <> 'learning' OR (expires_at IS NULL AND insight_topic IS NULL)",
            name="ck_learner_file_learning_shape",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_learner_file_confidence",
        ),
    )
    op.create_index(
        "ix_learner_file_profile_active",
        "learner_file_entries",
        ["language_profile_id", "deleted_at", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_learner_file_profile_active", table_name="learner_file_entries")
    op.drop_table("learner_file_entries")
