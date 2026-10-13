"""Use run identity instead of capture policy and schema versions.

Revision ID: 20261012_0014
Revises: 20261012_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261012_0014"
down_revision: str | None = "20261012_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_analysis_run_session_policy", "analysis_runs", type_="unique")
    op.drop_column("analysis_runs", "policy_version")
    op.drop_column("analysis_runs", "schema_version")
    op.create_index(
        "uq_analysis_run_pending_session",
        "analysis_runs",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_analysis_run_pending_session", table_name="analysis_runs")
    op.add_column("analysis_runs", sa.Column("schema_version", sa.String(64)))
    op.add_column("analysis_runs", sa.Column("policy_version", sa.String(64)))
    # Historical version values were discarded; unique run-based placeholders
    # restore the old constraint without removing any analysis or recap rows.
    op.execute(
        "UPDATE analysis_runs SET schema_version = 'legacy', "
        "policy_version = 'run-' || id::text"
    )
    op.alter_column("analysis_runs", "schema_version", nullable=False)
    op.alter_column("analysis_runs", "policy_version", nullable=False)
    op.create_unique_constraint(
        "uq_analysis_run_session_policy", "analysis_runs", ["session_id", "policy_version"]
    )
