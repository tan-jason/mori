"""Existing observations remain legacy; new evidence schema matches migrations."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from mori.persistence.base import Base
from mori.persistence.model_registry import load_models


def test_migration_preserves_legacy_observations_without_inventing_evidence(
    database_url: str,
) -> None:
    path = Path(__file__).parents[1] / "migrations/versions/0015_structured_learning_evidence.py"
    spec = importlib.util.spec_from_file_location("structured_evidence_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            # Transactional DDL isolates this upgrade fixture from the application's schema.
            db.execute(text("CREATE SCHEMA evidence_upgrade_test"))
            db.execute(text("SET LOCAL search_path TO evidence_upgrade_test"))
            db.execute(text("CREATE TABLE session_turns (id uuid PRIMARY KEY)"))
            db.execute(text("CREATE TABLE analysis_observations (id uuid PRIMARY KEY)"))
            db.execute(
                text(
                    "CREATE TABLE analysis_observation_turns "
                    "(observation_id uuid REFERENCES analysis_observations(id), "
                    "turn_id uuid REFERENCES session_turns(id), "
                    "PRIMARY KEY (observation_id, turn_id))"
                )
            )
            observation_id, turn_id = uuid4(), uuid4()
            db.execute(text("INSERT INTO session_turns VALUES (:id)"), {"id": turn_id})
            db.execute(
                text("INSERT INTO analysis_observations VALUES (:id)"), {"id": observation_id}
            )
            db.execute(
                text("INSERT INTO analysis_observation_turns VALUES (:observation, :turn)"),
                {"observation": observation_id, "turn": turn_id},
            )
            with Operations.context(MigrationContext.configure(db)):
                migration.upgrade()
            assert db.execute(
                text(
                    "SELECT id, curriculum_item_key, review_status, review_reason "
                    "FROM analysis_observations"
                )
            ).one() == (observation_id, None, "legacy", None)
            assert db.execute(
                text(
                    "SELECT learner_quote, learner_quote_start, opportunity_turn_id, assistance "
                    "FROM analysis_observation_turns"
                )
            ).one() == (None, None, None, None)
            with Operations.context(MigrationContext.configure(db)):
                migration.downgrade()
            assert [
                column["name"] for column in inspect(db).get_columns("analysis_observations")
            ] == ["id"]
            assert db.execute(
                text("SELECT observation_id, turn_id FROM analysis_observation_turns")
            ).one() == (observation_id, turn_id)
            db.execute(text("DROP SCHEMA evidence_upgrade_test CASCADE"))
    finally:
        engine.dispose()


def test_head_schema_matches_model_metadata(database_url: str) -> None:
    load_models()
    engine = create_engine(database_url)
    try:
        with engine.connect() as db:
            context = MigrationContext.configure(
                db,
                opts={
                    "compare_type": True,
                    "include_object": lambda _obj, name, kind, reflected, _comparison: (
                        not (kind == "table" and reflected and name.startswith("procrastinate_"))
                    ),
                },
            )
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()
