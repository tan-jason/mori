"""Add learner-authored learning intent before backfilling existing profiles.

Revision ID: 20261006_0009
Revises: 20261001_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0009"
down_revision: str | None = "20261001_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("learner_preferences", sa.Column("learning_goal", sa.String(500)))
    op.add_column("learner_preferences", sa.Column("speaking_context", sa.String(500)))
    op.add_column(
        "learner_preferences",
        sa.Column("learning_notes", sa.String(3000), server_default=""),
    )


def downgrade() -> None:
    op.drop_column("learner_preferences", "learning_notes")
    op.drop_column("learner_preferences", "speaking_context")
    op.drop_column("learner_preferences", "learning_goal")
