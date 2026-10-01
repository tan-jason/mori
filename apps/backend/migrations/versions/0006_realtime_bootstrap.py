"""Persist call bootstrap attempts before contacting the voice provider.

Revision ID: 20260930_0006
Revises: 20260929_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0006"
down_revision: str | None = "20260929_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_call_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("provider_call_id", sa.String(160), unique=True),
        sa.Column("pending_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt_number > 0", name="ck_session_call_attempt_number"),
        sa.CheckConstraint(
            "state IN ('bootstrap_pending', 'awaiting_client', 'active', 'ending', "
            "'ended', 'provider_failed', 'ambiguous', 'cleanup_pending')",
            name="ck_session_call_attempt_state",
        ),
        sa.UniqueConstraint("session_id", "attempt_number", name="uq_session_call_attempt_number"),
    )
    op.create_index(
        "uq_session_call_attempt_open",
        "session_call_attempts",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('bootstrap_pending', 'awaiting_client', 'active', 'ending', "
            "'ambiguous', 'cleanup_pending')"
        ),
    )
    op.create_index(
        "ix_session_call_attempt_recovery",
        "session_call_attempts",
        ["state", "pending_expires_at"],
    )
    op.create_table(
        "session_prompt_builds",
        sa.Column(
            "call_attempt_id",
            sa.Uuid(),
            sa.ForeignKey("session_call_attempts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("session_plans.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_policy_version", sa.String(64), nullable=False),
        sa.Column("pair_policy_version", sa.String(64), nullable=False),
        sa.Column("level_policy_version", sa.String(64), nullable=False),
        sa.Column("voice_policy_version", sa.String(64), nullable=False),
        sa.Column("model_alias", sa.String(128), nullable=False),
        sa.Column("voice_alias", sa.String(128), nullable=False),
        sa.Column("instructions_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("session_prompt_builds")
    op.drop_index("ix_session_call_attempt_recovery", table_name="session_call_attempts")
    op.drop_index("uq_session_call_attempt_open", table_name="session_call_attempts")
    op.drop_table("session_call_attempts")
