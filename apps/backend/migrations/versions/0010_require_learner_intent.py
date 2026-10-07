"""Require intent after existing profile rows are backfilled.

Revision ID: 20261006_0010
Revises: 20261006_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0010"
down_revision: str | None = "20261006_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    incomplete = connection.scalar(
        sa.text(
            "SELECT count(*) FROM learner_preferences WHERE learning_goal IS NULL "
            "OR length(btrim(learning_goal)) = 0 OR speaking_context IS NULL "
            "OR length(btrim(speaking_context)) = 0 OR learning_notes IS NULL"
        )
    )
    if incomplete:
        raise RuntimeError(
            "Backfill learner_preferences learning_goal, speaking_context, and "
            "learning_notes before upgrading to 20261006_0010"
        )
    op.alter_column("learner_preferences", "learning_goal", nullable=False)
    op.alter_column("learner_preferences", "speaking_context", nullable=False)
    op.alter_column("learner_preferences", "learning_notes", nullable=False)
    op.create_check_constraint(
        "ck_learner_preferences_learning_goal",
        "learner_preferences",
        "length(btrim(learning_goal)) > 0",
    )
    op.create_check_constraint(
        "ck_learner_preferences_speaking_context",
        "learner_preferences",
        "length(btrim(speaking_context)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_learner_preferences_speaking_context", "learner_preferences")
    op.drop_constraint("ck_learner_preferences_learning_goal", "learner_preferences")
    op.alter_column("learner_preferences", "learning_notes", nullable=True)
    op.alter_column("learner_preferences", "speaking_context", nullable=True)
    op.alter_column("learner_preferences", "learning_goal", nullable=True)
