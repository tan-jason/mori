"""Move shared course definitions to versioned application code.

Revision ID: 20260929_0005
Revises: 20260929_0004
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0005"
down_revision: str | None = "20260929_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Abort rather than discard course rows added outside the original seed data.
    connection = op.get_bind()
    expected_ids = {
        "course_catalog": set(range(1, 8)),
        "curriculum_versions": {100},
        "curriculum_items": set(range(101, 108)),
        "course_policies": {201, 202},
        "evidence_rules": set(range(1101, 1108)),
    }
    for table, expected in expected_ids.items():
        found = {row[0] for row in connection.execute(sa.text(f"SELECT id FROM {table}"))}
        if found != {UUID(int=value) for value in expected}:
            raise RuntimeError(f"unexpected {table} rows; preserve them before migration")

    # Preserve stable objective identity before removing the published item table.
    op.execute("DROP TRIGGER mori_guard_session_plan_objectives ON session_plan_objectives")
    op.add_column("session_plan_objectives", sa.Column("curriculum_item_key", sa.String(80)))
    op.execute("""
        UPDATE session_plan_objectives AS objective
        SET curriculum_item_key = item.key
        FROM curriculum_items AS item
        WHERE objective.curriculum_item_id = item.id
    """)
    op.drop_constraint("ck_plan_objective_kind", "session_plan_objectives", type_="check")
    op.drop_column("session_plan_objectives", "curriculum_item_id")
    op.create_check_constraint(
        "ck_plan_objective_kind",
        "session_plan_objectives",
        "kind IS NULL OR (kind = 'conversation_focus' AND curriculum_item_key IS NULL) "
        "OR (kind = 'graded' AND curriculum_item_key IS NOT NULL)",
    )
    op.execute("""
        CREATE TRIGGER mori_guard_session_plan_objectives
        BEFORE UPDATE ON session_plan_objectives
        FOR EACH ROW EXECUTE FUNCTION mori_reject_immutable_update()
    """)

    op.drop_constraint("ck_session_plans_v1_complete", "session_plans", type_="check")
    op.drop_column("session_plans", "curriculum_version_id")
    op.create_check_constraint(
        "ck_session_plans_v1_complete",
        "session_plans",
        "schema_version = 'legacy_placeholder' OR "
        "(schema_version = 'learning_plan_v1' AND mode IN ('learning', 'practice') "
        "AND profile_version IS NOT NULL AND preference_version IS NOT NULL "
        "AND settings_version IS NOT NULL AND setup_digest IS NOT NULL "
        "AND requested_words IS NOT NULL AND curriculum_version IS NOT NULL "
        "AND base_policy_version IS NOT NULL AND pair_policy_version IS NOT NULL "
        "AND level_policy_version IS NOT NULL "
        "AND ((mode = 'learning' AND selected_level IN ('beginner', 'intermediate', 'advanced')) "
        "OR (mode = 'practice' AND selected_level IS NULL)))",
    )

    op.drop_column("course_catalog", "active_curriculum_version_id")
    op.drop_table("evidence_rules")
    op.drop_table("curriculum_edges")
    op.drop_table("curriculum_items")
    op.drop_table("course_policies")
    op.drop_table("curriculum_versions")
    op.drop_table("course_catalog")
    op.execute("DROP FUNCTION mori_reject_published_course_change()")


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading the code curriculum migration would require restoring "
        "published course data that is now versioned in application code"
    )
