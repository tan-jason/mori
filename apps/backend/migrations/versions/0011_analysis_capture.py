"""Add transcript-grounded recap capture and the pinned Procrastinate queue.

Revision ID: 20261006_0011
Revises: 20261006_0010
"""

from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0011"
down_revision: str | None = "20261006_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    queue_schema = Path(__file__).resolve().parents[1] / "procrastinate_3_10_0.sql"
    # psycopg scans percent signs even in PL/pgSQL string literals.
    if op.get_bind().scalar(sa.text("SELECT to_regclass('public.procrastinate_jobs')")) is None:
        op.get_bind().exec_driver_sql(queue_schema.read_text().replace("%", "%%"))
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("extractor_model", sa.String(128), nullable=False),
        sa.Column("curriculum_version", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("final_turn_sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failure_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("session_id", "policy_version", name="uq_analysis_run_session_policy"),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed')", name="ck_analysis_run_status"
        ),
    )
    op.create_table(
        "recaps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_run_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recaps_session_created", "recaps", ["session_id", "created_at"])
    op.create_table(
        "analysis_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "analysis_run_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("detail", sa.String(240), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("analysis_run_id", "ordinal", name="uq_analysis_observation_ordinal"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_analysis_observation_confidence"
        ),
    )
    op.create_table(
        "analysis_observation_turns",
        sa.Column(
            "observation_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_observations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "turn_id",
            sa.Uuid(),
            sa.ForeignKey("session_turns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "analysis_corrections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "analysis_run_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "learner_turn_id",
            sa.Uuid(),
            sa.ForeignKey("session_turns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("suggestion", sa.String(240), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("analysis_run_id", "ordinal", name="uq_analysis_correction_ordinal"),
    )


def downgrade() -> None:
    op.drop_table("analysis_corrections")
    op.drop_table("analysis_observation_turns")
    op.drop_table("analysis_observations")
    op.drop_table("recaps")
    op.drop_table("analysis_runs")
    # Queue objects are shared infrastructure. Keep them on downgrade so another
    # worker's jobs are not destroyed by reversing this application migration.
