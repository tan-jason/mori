"""Create reserved voice-session and immutable plan foundations.

Revision ID: 20260924_0002
Revises: 20260903_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0002"
down_revision: str | None = "20260903_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("creation_key_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("connected_limit_ms", sa.Integer(), nullable=False),
        sa.Column("connected_ms", sa.Integer(), nullable=False),
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(length=64), nullable=True),
        sa.Column("final_turn_sequence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("row_version > 0", name="ck_sessions_row_version"),
        sa.CheckConstraint("connected_limit_ms > 0", name="ck_sessions_connected_limit"),
        sa.CheckConstraint("connected_ms >= 0", name="ck_sessions_connected_ms"),
        sa.CheckConstraint(
            "state IN ('created', 'reserved', 'planned', 'connecting', 'active', "
            "'reconnecting', 'ending', "
            "'analysis_pending', 'ready', 'analysis_failed', 'setup_failed')",
            name="ck_sessions_state",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "creation_key_digest", name="uq_sessions_user_creation_key"),
    )
    op.create_index(
        "ix_sessions_profile_created", "sessions", ["language_profile_id", "created_at"]
    )
    op.create_index("ix_sessions_state_expiry", "sessions", ["state", "session_expires_at"])

    op.create_table(
        "session_plans",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_version", sa.String(length=64), nullable=False),
        sa.Column("selection_rule_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("objective_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "objective_count BETWEEN 1 AND 3", name="ck_session_plans_objective_count"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_table(
        "session_plan_objectives",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint("ordinal BETWEEN 1 AND 3", name="ck_session_plan_objectives_ordinal"),
        sa.ForeignKeyConstraint(["session_id"], ["session_plans.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "ordinal"),
    )

    op.create_table(
        "usage_reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("grant_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('reserved', 'consumed', 'released')", name="ck_usage_reservations_state"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grant_id"], ["grants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(
        "uq_usage_reservations_grant_reserved",
        "usage_reservations",
        ["grant_id"],
        unique=True,
        postgresql_where=sa.text("state = 'reserved'"),
    )
    op.create_index(
        "ix_usage_reservations_state_expiry", "usage_reservations", ["state", "expires_at"]
    )

    op.create_table(
        "usage_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('reserved', 'consumed', 'released', 'corrected')",
            name="ck_usage_events_kind",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["usage_reservations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_usage_events_reservation_created", "usage_events", ["reservation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_reservation_created", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_index("ix_usage_reservations_state_expiry", table_name="usage_reservations")
    op.drop_index("uq_usage_reservations_grant_reserved", table_name="usage_reservations")
    op.drop_table("usage_reservations")
    op.drop_table("session_plan_objectives")
    op.drop_table("session_plans")
    op.drop_index("ix_sessions_state_expiry", table_name="sessions")
    op.drop_index("ix_sessions_profile_created", table_name="sessions")
    op.drop_table("sessions")
