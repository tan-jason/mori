"""Publish the first course and support versioned, immutable session plans.

Revision ID: 20260929_0004
Revises: 20260926_0003
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260929_0004"
down_revision: str | None = "20260926_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COURSE_ID = UUID(int=1)
VERSION_ID = UUID(int=100)
CURRICULUM_VERSION = "mandarin-foundations-v1"
PAIR_POLICY_VERSION = "en-zh-pair-v1"
VOICE_POLICY_VERSION = "mandarin-voice-v1"
ITEMS = (
    (
        101,
        "beginner-check-in",
        "Share a simple introduction and answer a follow-up.",
        "beginner",
        "diagnostic",
        1,
        ["introduction"],
        [],
        "你好，我叫……。你呢？",
    ),
    (
        102,
        "greetings",
        "Greet someone and introduce yourself in Mandarin.",
        "beginner",
        "skill",
        2,
        ["introduction", "people"],
        ["hello", "name"],
        "你好。我叫……。很高兴认识你。",
    ),
    (
        103,
        "daily-routine",
        "Describe one part of your day in Mandarin.",
        "beginner",
        "skill",
        3,
        ["daily life", "weekend"],
        ["today", "morning"],
        "今天早上我……。",
    ),
    (
        104,
        "intermediate-check-in",
        "Describe a recent event and answer a follow-up.",
        "intermediate",
        "diagnostic",
        1,
        ["weekend", "travel"],
        [],
        "上周末我去了……，然后……。",
    ),
    (
        105,
        "past-event",
        "Tell a short story about a recent event.",
        "intermediate",
        "skill",
        2,
        ["weekend", "travel"],
        ["yesterday", "market"],
        "昨天我去了市场，买了……。",
    ),
    (
        106,
        "advanced-check-in",
        "Explain an opinion and respond to a different view.",
        "advanced",
        "diagnostic",
        1,
        ["opinions"],
        [],
        "我认为……，因为……。你怎么看？",
    ),
    (
        107,
        "reasoned-opinion",
        "Support an opinion with a reason and an example.",
        "advanced",
        "skill",
        2,
        ["opinions", "work"],
        ["because", "however"],
        "我认为……，因为……。不过，也可以说……。",
    ),
)


def upgrade() -> None:
    versions = op.create_table(
        "curriculum_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "course_catalog_id",
            sa.Uuid(),
            sa.ForeignKey("course_catalog.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("course_catalog_id", "version", name="uq_curriculum_course_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="ck_curriculum_status"
        ),
    )
    op.add_column(
        "course_catalog",
        sa.Column(
            "active_curriculum_version_id",
            sa.Uuid(),
            sa.ForeignKey("curriculum_versions.id", ondelete="RESTRICT"),
        ),
    )
    policies = op.create_table(
        "course_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "course_catalog_id",
            sa.Uuid(),
            sa.ForeignKey("course_catalog.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "course_catalog_id", "kind", "version", name="uq_course_policy_version"
        ),
        sa.CheckConstraint("kind IN ('pair', 'voice')", name="ck_course_policy_kind"),
    )
    items = op.create_table(
        "curriculum_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "curriculum_version_id",
            sa.Uuid(),
            sa.ForeignKey("curriculum_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("target_language_content", sa.Text(), nullable=False),
        sa.Column("level", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("selection_weight", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("topic_tags", JSONB(), nullable=False),
        sa.Column("word_tags", JSONB(), nullable=False),
        sa.UniqueConstraint("curriculum_version_id", "key", name="uq_curriculum_item_key"),
        sa.UniqueConstraint("curriculum_version_id", "id", name="uq_curriculum_item_version_id"),
        sa.CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')", name="ck_curriculum_item_level"
        ),
        sa.CheckConstraint(
            "kind IN ('vocabulary', 'grammar', 'conversation', 'pronunciation')",
            name="ck_curriculum_item_kind",
        ),
        sa.CheckConstraint("purpose IN ('diagnostic', 'skill')", name="ck_curriculum_item_purpose"),
        sa.CheckConstraint("selection_weight > 0", name="ck_curriculum_item_weight"),
    )
    edges = op.create_table(
        "curriculum_edges",
        sa.Column(
            "curriculum_version_id",
            sa.Uuid(),
            sa.ForeignKey("curriculum_versions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "prerequisite_item_id",
            sa.Uuid(),
            primary_key=True,
        ),
        sa.Column(
            "dependent_item_id",
            sa.Uuid(),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.CheckConstraint("kind = 'requires'", name="ck_curriculum_edge_kind"),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id", "prerequisite_item_id"],
            ["curriculum_items.curriculum_version_id", "curriculum_items.id"],
            name="fk_curriculum_edge_prerequisite_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id", "dependent_item_id"],
            ["curriculum_items.curriculum_version_id", "curriculum_items.id"],
            name="fk_curriculum_edge_dependent_version",
            ondelete="RESTRICT",
        ),
    )
    rules = op.create_table(
        "evidence_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "curriculum_version_id",
            sa.Uuid(),
            sa.ForeignKey("curriculum_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "curriculum_item_id",
            sa.Uuid(),
            nullable=False,
            unique=True,
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id", "curriculum_item_id"],
            ["curriculum_items.curriculum_version_id", "curriculum_items.id"],
            name="fk_evidence_rule_item_version",
            ondelete="RESTRICT",
        ),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("evidence_kind", sa.String(32), nullable=False),
        sa.Column("minimum_distinct_turns", sa.Integer(), nullable=False),
        sa.Column("confidence_threshold", sa.Float(), nullable=False),
        sa.Column("mastery_threshold", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("requirement", sa.Text(), nullable=False),
    )

    op.add_column("sessions", sa.Column("request_digest", sa.String(64)))
    op.add_column(
        "session_plans",
        sa.Column(
            "schema_version", sa.String(32), server_default="legacy_placeholder", nullable=False
        ),
    )
    op.alter_column("session_plans", "schema_version", server_default="learning_plan_v1")
    op.add_column("session_plans", sa.Column("mode", sa.String(16)))
    op.add_column("session_plans", sa.Column("snapshot_id", sa.Uuid()))
    op.add_column("session_plans", sa.Column("profile_version", sa.Integer()))
    op.add_column("session_plans", sa.Column("preference_version", sa.Integer()))
    op.add_column("session_plans", sa.Column("settings_version", sa.Integer()))
    op.add_column("session_plans", sa.Column("selected_level", sa.String(32)))
    op.add_column("session_plans", sa.Column("topic", sa.String(160)))
    op.add_column("session_plans", sa.Column("requested_words", JSONB()))
    op.create_check_constraint(
        "ck_session_plans_requested_words_array",
        "session_plans",
        "requested_words IS NULL OR jsonb_typeof(requested_words) = 'array'",
    )
    op.add_column("session_plans", sa.Column("setup_digest", sa.String(64)))
    op.add_column(
        "session_plans",
        sa.Column(
            "curriculum_version_id",
            sa.Uuid(),
            sa.ForeignKey("curriculum_versions.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column("session_plans", sa.Column("base_policy_version", sa.String(64)))
    op.add_column("session_plans", sa.Column("pair_policy_version", sa.String(64)))
    op.add_column("session_plans", sa.Column("level_policy_version", sa.String(64)))
    op.create_check_constraint(
        "ck_session_plans_v1_complete",
        "session_plans",
        "schema_version = 'legacy_placeholder' OR "
        "(schema_version = 'learning_plan_v1' AND mode IN ('learning', 'practice') "
        "AND profile_version IS NOT NULL AND preference_version IS NOT NULL "
        "AND settings_version IS NOT NULL AND setup_digest IS NOT NULL "
        "AND requested_words IS NOT NULL "
        "AND curriculum_version_id IS NOT NULL AND base_policy_version IS NOT NULL "
        "AND pair_policy_version IS NOT NULL AND level_policy_version IS NOT NULL "
        "AND ((mode = 'learning' AND selected_level IN ('beginner', 'intermediate', 'advanced')) "
        "OR (mode = 'practice' AND selected_level IS NULL)))",
    )
    op.add_column("session_plan_objectives", sa.Column("kind", sa.String(32)))
    op.add_column(
        "session_plan_objectives",
        sa.Column(
            "curriculum_item_id",
            sa.Uuid(),
            sa.ForeignKey("curriculum_items.id", ondelete="RESTRICT"),
        ),
    )
    op.create_check_constraint(
        "ck_plan_objective_kind",
        "session_plan_objectives",
        "kind IS NULL OR (kind = 'conversation_focus' AND curriculum_item_id IS NULL) "
        "OR (kind = 'graded' AND curriculum_item_id IS NOT NULL)",
    )

    now = datetime(2026, 9, 29, tzinfo=UTC)
    op.bulk_insert(
        versions,
        [
            {
                "id": VERSION_ID,
                "course_catalog_id": COURSE_ID,
                "version": CURRICULUM_VERSION,
                "content_digest": sha256(
                    json.dumps(
                        {
                            "items": ITEMS,
                            "edges": ((101, 102), (102, 103), (104, 105), (106, 107)),
                            "evidenceRuleVersion": "transcript-v1",
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "status": "published",
                "published_at": now,
            }
        ],
    )
    op.bulk_insert(
        policies,
        [
            {
                "id": UUID(int=201),
                "course_catalog_id": COURSE_ID,
                "kind": "pair",
                "version": PAIR_POLICY_VERSION,
                "content": (
                    "Use Standard Mandarin for examples and spoken practice. "
                    "Give brief English rescue scaffolds when understanding breaks down. "
                    "Give Mandarin-specific pronunciation guidance only when the signal is clear; "
                    "model one repair and invite a retry."
                ),
                "published_at": now,
            },
            {
                "id": UUID(int=202),
                "course_catalog_id": COURSE_ID,
                "kind": "voice",
                "version": VOICE_POLICY_VERSION,
                "content": (
                    "Target spoken language: Standard Mandarin. Base language for brief "
                    "explanations: English. Playback pace follows learner preference "
                    "independently of accent."
                ),
                "published_at": now,
            },
        ],
    )
    op.bulk_insert(
        items,
        [
            {
                "id": UUID(int=row[0]),
                "curriculum_version_id": VERSION_ID,
                "key": row[1],
                "label": row[2],
                "target_language_content": row[8],
                "level": row[3],
                "kind": "conversation",
                "purpose": row[4],
                "selection_weight": row[5],
                "enabled": True,
                "topic_tags": row[6],
                "word_tags": row[7],
            }
            for row in ITEMS
        ],
    )
    op.bulk_insert(
        edges,
        [
            {
                "curriculum_version_id": VERSION_ID,
                "prerequisite_item_id": UUID(int=a),
                "dependent_item_id": UUID(int=b),
                "kind": "requires",
            }
            for a, b in ((101, 102), (102, 103), (104, 105), (106, 107))
        ],
    )
    op.bulk_insert(
        rules,
        [
            {
                "id": UUID(int=row[0] + 1000),
                "curriculum_version_id": VERSION_ID,
                "curriculum_item_id": UUID(int=row[0]),
                "version": "transcript-v1",
                "evidence_kind": "use",
                "minimum_distinct_turns": 1,
                "confidence_threshold": 1.0,
                "mastery_threshold": 1.0,
                "enabled": False,
                "requirement": (
                    "Accept only learner speech cited to an exact finalized turn. "
                    "Require a relevant response and a clear follow-up where the objective asks "
                    "for one. Do not infer pronunciation mastery from transcript text."
                ),
            }
            for row in ITEMS
        ],
    )
    op.execute(
        sa.text(
            "UPDATE course_catalog SET active_curriculum_version = :curriculum, "
            "active_curriculum_version_id = :version_id, "
            "pair_policy_version = :pair, voice_policy_version = :voice WHERE id = :id"
        ).bindparams(
            curriculum=CURRICULUM_VERSION,
            version_id=VERSION_ID,
            pair=PAIR_POLICY_VERSION,
            voice=VOICE_POLICY_VERSION,
            id=COURSE_ID,
        )
    )
    op.drop_constraint("ck_course_catalog_published_bundle", "course_catalog")
    op.create_check_constraint(
        "ck_course_catalog_published_bundle",
        "course_catalog",
        "status != 'published' OR (active_curriculum_version IS NOT NULL "
        "AND active_curriculum_version_id IS NOT NULL AND pair_policy_version IS NOT NULL "
        "AND voice_policy_version IS NOT NULL AND published_at IS NOT NULL)",
    )
    op.execute("""
        CREATE FUNCTION mori_reject_published_course_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE version_id uuid;
        BEGIN
            IF TG_TABLE_NAME = 'curriculum_versions' THEN
                IF OLD.status = 'published' THEN
                    RAISE EXCEPTION 'published curriculum version is immutable';
                END IF;
            ELSE
                version_id := CASE WHEN TG_OP = 'INSERT' THEN NEW.curriculum_version_id
                                   ELSE OLD.curriculum_version_id END;
                IF EXISTS (SELECT 1 FROM curriculum_versions
                           WHERE id = version_id AND status = 'published') THEN
                    RAISE EXCEPTION 'published curriculum content is immutable';
                END IF;
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END $$
    """)
    for table in ("curriculum_versions", "curriculum_items", "curriculum_edges", "evidence_rules"):
        events = (
            "UPDATE OR DELETE" if table == "curriculum_versions" else "INSERT OR UPDATE OR DELETE"
        )
        op.execute(
            f"CREATE TRIGGER mori_guard_{table} BEFORE {events} ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION mori_reject_published_course_change()"
        )
    op.execute("""
        CREATE FUNCTION mori_reject_immutable_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'published policy or session plan is immutable';
        END $$
    """)
    for table in ("course_policies", "session_plans", "session_plan_objectives"):
        events = "UPDATE OR DELETE" if table == "course_policies" else "UPDATE"
        op.execute(
            f"CREATE TRIGGER mori_guard_{table} BEFORE {events} ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION mori_reject_immutable_update()"
        )


def downgrade() -> None:
    for table in (
        "curriculum_versions",
        "curriculum_items",
        "curriculum_edges",
        "evidence_rules",
        "course_policies",
        "session_plans",
        "session_plan_objectives",
    ):
        op.execute(f"DROP TRIGGER mori_guard_{table} ON {table}")
    op.execute("DROP FUNCTION mori_reject_published_course_change()")
    op.execute("DROP FUNCTION mori_reject_immutable_update()")
    op.drop_constraint("ck_course_catalog_published_bundle", "course_catalog")
    op.execute(
        sa.text(
            "UPDATE course_catalog SET active_curriculum_version = 'm2-placeholder-v1', "
            "active_curriculum_version_id = NULL, "
            "pair_policy_version = 'm2-placeholder-v1', "
            "voice_policy_version = 'm2-placeholder-v1' WHERE id = :id"
        ).bindparams(id=COURSE_ID)
    )
    op.create_check_constraint(
        "ck_course_catalog_published_bundle",
        "course_catalog",
        "status != 'published' OR (active_curriculum_version IS NOT NULL "
        "AND pair_policy_version IS NOT NULL AND voice_policy_version IS NOT NULL "
        "AND published_at IS NOT NULL)",
    )
    op.drop_constraint("ck_plan_objective_kind", "session_plan_objectives")
    op.drop_column("session_plan_objectives", "curriculum_item_id")
    op.drop_column("session_plan_objectives", "kind")
    op.drop_constraint("ck_session_plans_v1_complete", "session_plans")
    op.drop_constraint("ck_session_plans_requested_words_array", "session_plans")
    for column in (
        "level_policy_version",
        "pair_policy_version",
        "base_policy_version",
        "curriculum_version_id",
        "setup_digest",
        "topic",
        "requested_words",
        "selected_level",
        "settings_version",
        "preference_version",
        "profile_version",
        "snapshot_id",
        "mode",
        "schema_version",
    ):
        op.drop_column("session_plans", column)
    op.drop_column("sessions", "request_digest")
    op.drop_table("evidence_rules")
    op.drop_table("curriculum_edges")
    op.drop_table("curriculum_items")
    op.drop_table("course_policies")
    op.drop_column("course_catalog", "active_curriculum_version_id")
    op.drop_table("curriculum_versions")
