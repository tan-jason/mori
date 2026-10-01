"""Add durable call deadlines, ownership, and transcript turns.

Revision ID: 20260930_0007
Revises: 20260930_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0007"
down_revision: str | None = "20260930_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in (
        "hard_deadline_at",
        "client_ack_deadline_at",
        "connected_at",
        "end_requested_at",
        "sideband_ready_at",
        "lease_until",
    ):
        op.add_column("session_call_attempts", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("session_call_attempts", sa.Column("lease_owner", sa.Uuid()))
    op.add_column(
        "session_call_attempts",
        sa.Column("transcript_gap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_session_call_attempt_lease", "session_call_attempts", ["state", "lease_until"]
    )
    op.create_table(
        "session_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_item_id", sa.String(160), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "provider_item_id", "role", name="uq_session_turn_item_role"
        ),
        sa.UniqueConstraint("session_id", "sequence", name="uq_session_turn_sequence"),
        sa.CheckConstraint("sequence > 0", name="ck_session_turn_sequence"),
        sa.CheckConstraint("role IN ('learner', 'tutor')", name="ck_session_turn_role"),
    )


def downgrade() -> None:
    op.drop_table("session_turns")
    op.drop_index("ix_session_call_attempt_lease", table_name="session_call_attempts")
    op.drop_column("session_call_attempts", "transcript_gap")
    for name in (
        "lease_owner",
        "lease_until",
        "end_requested_at",
        "sideband_ready_at",
        "connected_at",
        "client_ack_deadline_at",
        "hard_deadline_at",
    ):
        op.drop_column("session_call_attempts", name)
