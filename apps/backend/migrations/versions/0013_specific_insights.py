"""Permit multiple specific insights from one turn and digest based suppression.

Revision ID: 20261012_0013
Revises: 20261007_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261012_0013"
down_revision: str | None = "20261007_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "learner_file_entries_source_turn_id_key", "learner_file_entries", type_="unique"
    )
    op.add_column("learner_file_entries", sa.Column("fact_digest", sa.String(64)))
    op.create_index(
        "ix_learner_file_profile_fact",
        "learner_file_entries",
        ["language_profile_id", "fact_digest"],
    )


def downgrade() -> None:
    op.drop_index("ix_learner_file_profile_fact", table_name="learner_file_entries")
    op.drop_column("learner_file_entries", "fact_digest")
    op.create_unique_constraint(
        "learner_file_entries_source_turn_id_key", "learner_file_entries", ["source_turn_id"]
    )
