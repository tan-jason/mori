"""Track recoverable, attempt-scoped timed wrap-up delivery.

Revision ID: 20261013_0016
Revises: 20261012_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_0016"
down_revision: str | None = "20261012_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_controls",
        sa.Column(
            "call_attempt_id",
            sa.Uuid(),
            sa.ForeignKey("session_call_attempts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider_item_id", sa.String(160), nullable=False, unique=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_event_id", sa.String(160)),
        sa.Column("request_kind", sa.String(16)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'uncertain', 'acknowledged', 'failed')",
            name="ck_session_control_state",
        ),
        sa.CheckConstraint(
            "request_kind IS NULL OR request_kind IN ('create', 'retrieve')",
            name="ck_session_control_request_kind",
        ),
        sa.CheckConstraint(
            "(state = 'acknowledged') = (acknowledged_at IS NOT NULL)",
            name="ck_session_control_acknowledged",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_session_control_attempt_count"),
    )


def downgrade() -> None:
    op.drop_table("session_controls")
