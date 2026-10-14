"""lesson cycle persistence

Revision ID: 20261013_0017
Revises: 20261013_0016
Create Date: 2026-10-13 02:58:54.919649
"""

from collections.abc import Sequence
from hashlib import sha256

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261013_0017"
down_revision: str | None = "20261013_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "profile_learning_states",
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("history_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active_lesson_key", sa.String(length=120), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("history_revision >= 0", name="ck_profile_learning_revision"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("language_profile_id"),
    )
    op.create_table(
        "language_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("form", sa.String(length=240), nullable=False),
        sa.Column("meaning", sa.String(length=240), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("capability_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("introduced_session_id", sa.Uuid(), nullable=False),
        sa.Column("introduced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "jsonb_typeof(capability_keys) = 'array'", name="ck_language_item_capabilities"
        ),
        sa.CheckConstraint("kind IN ('word', 'phrase', 'move')", name="ck_language_item_kind"),
        sa.ForeignKeyConstraint(["introduced_session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_language_item_profile",
        "language_items",
        ["language_profile_id", "suppressed_at"],
        unique=False,
    )
    op.create_table(
        "analysis_decision_reviews",
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("analysis_run_id"),
    )
    op.create_table(
        "learning_contributions",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("history_revision", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lesson_key", sa.String(length=120), nullable=False),
        sa.Column("content_version", sa.String(length=64), nullable=False),
        sa.Column("accepted_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("analysis_run_id"),
    )
    op.create_index(
        op.f("ix_learning_contributions_language_profile_id"),
        "learning_contributions",
        ["language_profile_id"],
        unique=False,
    )
    op.create_table(
        "learning_occurrences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("lesson_key", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=True),
        sa.Column("capability_key", sa.String(length=120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('introduction', 'item_practice', 'capability_attempt')",
            name="ck_learning_occurrence_kind",
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["language_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_run_id", "ordinal", name="uq_learning_occurrence_ordinal"),
    )
    op.create_index(
        "ix_learning_occurrence_item",
        "learning_occurrences",
        ["item_id", "session_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_occurrence_profile_source",
        "learning_occurrences",
        ["language_profile_id", "session_id"],
        unique=False,
    )
    op.create_table(
        "lesson_benchmarks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("source_analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_key", sa.String(length=120), nullable=False),
        sa.Column("content_version", sa.String(length=64), nullable=False),
        sa.Column("rubric_version", sa.String(length=64), nullable=False),
        sa.Column("history_revision", sa.Integer(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("distributions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lesson_benchmark_profile_revision",
        "lesson_benchmarks",
        ["language_profile_id", "history_revision"],
        unique=False,
    )
    op.create_table(
        "session_learning_plans",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("language_profile_id", sa.Uuid(), nullable=False),
        sa.Column("source_history_revision", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("lesson_key", sa.String(length=120), nullable=False),
        sa.Column("content_version", sa.String(length=64), nullable=False),
        sa.Column("rubric_version", sa.String(length=64), nullable=False),
        sa.Column("focus_capability_key", sa.String(length=120), nullable=False),
        sa.Column("recall_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("new_item_maximum", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("new_item_maximum BETWEEN 1 AND 5", name="ck_learning_plan_allowance"),
        sa.CheckConstraint("source_history_revision >= 0", name="ck_learning_plan_revision"),
        sa.ForeignKeyConstraint(
            ["language_profile_id"], ["language_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["session_plans.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_table(
        "user_insights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_session_id", sa.Uuid(), nullable=False),
        sa.Column("source_turn_id", sa.Uuid(), nullable=True),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("source_quote_start", sa.Integer(), nullable=True),
        sa.Column("source_quote_end", sa.Integer(), nullable=True),
        sa.Column("temporal_context", sa.String(length=240), nullable=True),
        sa.Column("identity_digest", sa.String(length=64), nullable=False),
        sa.Column("edited_identity_digest", sa.String(length=64), nullable=True),
        sa.Column("legacy_fact_digest", sa.String(length=64), nullable=True),
        sa.Column(
            "suppressed_identity_digests",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("text", sa.String(length=240), nullable=True),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("origin IN ('capture', 'learner_edit')", name="ck_user_insight_origin"),
        sa.CheckConstraint(
            "text IS NOT NULL OR deleted_at IS NOT NULL", name="ck_user_insight_deleted"
        ),
        sa.CheckConstraint("version > 0", name="ck_user_insight_version"),
        sa.ForeignKeyConstraint(["source_session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_turn_id"], ["session_turns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_insight_active",
        "user_insights",
        ["user_id", "deleted_at", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_user_insight_identity", "user_insights", ["user_id", "identity_digest"], unique=False
    )
    op.add_column("learner_file_entries", sa.Column("language_item_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_learner_file_language_item",
        "learner_file_entries",
        "language_items",
        ["language_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "session_prompt_builds",
        sa.Column(
            "redacted_recall_item_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.add_column(
        "session_prompt_builds", sa.Column("source_history_revision", sa.Integer(), nullable=True)
    )

    op.execute(
        "CREATE TRIGGER mori_guard_session_learning_plans BEFORE UPDATE ON session_learning_plans "
        "FOR EACH ROW EXECUTE FUNCTION mori_reject_immutable_update()"
    )
    _migrate_user_insights()


def _migrate_user_insights() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("""
        SELECT e.*, p.user_id FROM learner_file_entries e
        JOIN language_profiles p ON p.id=e.language_profile_id WHERE e.kind='insight'
    """)
    ).mappings()
    for row in rows:
        # Deleted legacy text may have been erased. Preserve its old digest as a
        # tombstone for runtime compatibility checks using the original secret.
        text = row["text"]
        canonical = " ".join((text or row["fact_digest"] or str(row["id"])).casefold().split())
        identity = sha256(f"{row['user_id']}:{canonical}:".encode()).hexdigest()
        quote = None
        if row["source_turn_id"] is not None:
            quote = connection.scalar(
                sa.text("SELECT text FROM session_turns WHERE id=:id"),
                {"id": row["source_turn_id"]},
            )
        connection.execute(
            sa.text("""
            INSERT INTO user_insights (id,user_id,source_session_id,source_turn_id,source_quote,
                source_quote_start,source_quote_end,identity_digest,legacy_fact_digest,text,origin,
                version,created_at,updated_at,expires_at,deleted_at)
            VALUES (:id,:user_id,:source_session_id,:source_turn_id,:quote,:start,:end,:identity,
                :fact_digest,:text,:origin,:version,:created_at,:updated_at,:expires_at,:deleted_at)
        """),
            {
                **row,
                "quote": quote,
                "start": 0 if quote else None,
                "end": len(quote) if quote else None,
                "identity": identity,
            },
        )


def downgrade() -> None:
    # Preserve corrections and deletions to migrated records on rollback.
    op.execute("""UPDATE learner_file_entries e SET text=i.text, origin=i.origin, version=i.version,
        updated_at=i.updated_at, expires_at=i.expires_at, deleted_at=i.deleted_at
        FROM user_insights i WHERE e.id=i.id AND e.kind='insight'""")
    op.execute("DROP TRIGGER mori_guard_session_learning_plans ON session_learning_plans")

    op.drop_column("session_prompt_builds", "source_history_revision")
    op.drop_column("session_prompt_builds", "redacted_recall_item_ids")
    op.drop_constraint("fk_learner_file_language_item", "learner_file_entries", type_="foreignkey")
    op.drop_column("learner_file_entries", "language_item_id")
    op.drop_index("ix_user_insight_identity", table_name="user_insights")
    op.drop_index("ix_user_insight_active", table_name="user_insights")
    op.drop_table("user_insights")
    op.drop_table("session_learning_plans")
    op.drop_index("ix_lesson_benchmark_profile_revision", table_name="lesson_benchmarks")
    op.drop_table("lesson_benchmarks")
    op.drop_index("ix_learning_occurrence_profile_source", table_name="learning_occurrences")
    op.drop_index("ix_learning_occurrence_item", table_name="learning_occurrences")
    op.drop_table("learning_occurrences")
    op.drop_index(
        op.f("ix_learning_contributions_language_profile_id"), table_name="learning_contributions"
    )
    op.drop_table("learning_contributions")
    op.drop_table("analysis_decision_reviews")
    op.drop_index("ix_language_item_profile", table_name="language_items")
    op.drop_table("language_items")
    op.drop_table("profile_learning_states")
