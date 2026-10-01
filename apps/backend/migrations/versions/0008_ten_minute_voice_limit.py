"""Set the introductory voice entitlement to ten minutes.

Revision ID: 20261001_0008
Revises: 20260930_0007
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "20261001_0008"
down_revision: str | None = "20260930_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INTRO_RULE_ID = UUID("6a6e1b0d-b750-4ccb-9185-a5b06879df2f")


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE entitlement_rules SET max_duration_seconds = 600 "
            "WHERE id = :rule_id"
        ).bindparams(sa.bindparam("rule_id", _INTRO_RULE_ID, type_=sa.Uuid()))
    )
    op.execute(
        sa.text(
            "UPDATE sessions SET connected_limit_ms = 600000 "
            "WHERE state = 'planned' AND connected_limit_ms > 600000"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE entitlement_rules SET max_duration_seconds = 1200 "
            "WHERE id = :rule_id"
        ).bindparams(sa.bindparam("rule_id", _INTRO_RULE_ID, type_=sa.Uuid()))
    )
