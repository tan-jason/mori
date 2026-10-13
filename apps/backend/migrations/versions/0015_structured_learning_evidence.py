"""Preserve quoted practice evidence and semantic review context.

Revision ID: 20261012_0015
Revises: 20261012_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261012_0015"
down_revision: str | None = "20261012_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analysis_observations", sa.Column("curriculum_item_key", sa.String(128)))
    op.add_column(
        "analysis_observations",
        sa.Column("review_status", sa.String(16), nullable=False, server_default="legacy"),
    )
    op.add_column("analysis_observations", sa.Column("review_reason", sa.String(240)))
    op.create_check_constraint(
        "ck_analysis_observation_review_status",
        "analysis_observations",
        "review_status IN ('legacy', 'supported')",
    )
    op.create_check_constraint(
        "ck_analysis_observation_review_context",
        "analysis_observations",
        "review_status <> 'supported' OR "
        "(curriculum_item_key IS NOT NULL AND review_reason IS NOT NULL "
        "AND length(trim(review_reason)) > 0)",
    )
    for name, column_type in (
        ("learner_quote", sa.String(200)),
        ("learner_quote_start", sa.Integer()),
        ("learner_quote_end", sa.Integer()),
        ("opportunity_turn_id", sa.Uuid()),
        ("opportunity_quote", sa.String(200)),
        ("opportunity_quote_start", sa.Integer()),
        ("opportunity_quote_end", sa.Integer()),
        ("assistance", sa.String(16)),
    ):
        op.add_column("analysis_observation_turns", sa.Column(name, column_type))
    op.create_foreign_key(
        "fk_analysis_evidence_opportunity",
        "analysis_observation_turns",
        "session_turns",
        ["opportunity_turn_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_analysis_evidence_learner_turn", "analysis_observation_turns", ["turn_id"])
    op.create_index(
        "ix_analysis_evidence_opportunity", "analysis_observation_turns", ["opportunity_turn_id"]
    )
    op.create_check_constraint(
        "ck_analysis_evidence_learner_span",
        "analysis_observation_turns",
        "(learner_quote IS NULL AND learner_quote_start IS NULL "
        "AND learner_quote_end IS NULL AND assistance IS NULL "
        "AND opportunity_turn_id IS NULL) OR "
        "(learner_quote IS NOT NULL AND learner_quote_start IS NOT NULL "
        "AND learner_quote_end IS NOT NULL AND learner_quote_start >= 0 "
        "AND learner_quote_end > learner_quote_start "
        "AND learner_quote_end - learner_quote_start = char_length(learner_quote) "
        "AND assistance IS NOT NULL "
        "AND assistance IN ('independent', 'cued', 'modelled', 'unknown'))",
    )
    op.create_check_constraint(
        "ck_analysis_evidence_opportunity_span",
        "analysis_observation_turns",
        "(opportunity_turn_id IS NULL AND opportunity_quote IS NULL "
        "AND opportunity_quote_start IS NULL AND opportunity_quote_end IS NULL) OR "
        "(opportunity_turn_id IS NOT NULL AND opportunity_quote IS NOT NULL "
        "AND opportunity_quote_start IS NOT NULL AND opportunity_quote_end IS NOT NULL "
        "AND opportunity_quote_start >= 0 AND opportunity_quote_end > opportunity_quote_start "
        "AND opportunity_quote_end - opportunity_quote_start = char_length(opportunity_quote))",
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_evidence_opportunity", table_name="analysis_observation_turns")
    op.drop_index("ix_analysis_evidence_learner_turn", table_name="analysis_observation_turns")
    op.drop_constraint("ck_analysis_evidence_opportunity_span", "analysis_observation_turns")
    op.drop_constraint("ck_analysis_evidence_learner_span", "analysis_observation_turns")
    op.drop_constraint("fk_analysis_evidence_opportunity", "analysis_observation_turns")
    for name in (
        "assistance",
        "opportunity_quote_end",
        "opportunity_quote_start",
        "opportunity_quote",
        "opportunity_turn_id",
        "learner_quote_end",
        "learner_quote_start",
        "learner_quote",
    ):
        op.drop_column("analysis_observation_turns", name)
    op.drop_constraint("ck_analysis_observation_review_context", "analysis_observations")
    op.drop_constraint("ck_analysis_observation_review_status", "analysis_observations")
    for name in ("review_reason", "review_status", "curriculum_item_key"):
        op.drop_column("analysis_observations", name)
