"""Insight ownership migration preserves edits, expiry, and erased tombstones."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def test_user_insight_upgrade_rollback_and_reupgrade_preserve_controls(database_url: str) -> None:
    name = f"mori_cycle_migration_{uuid4().hex}"
    admin = create_engine(database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as db:
        db.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(database_url).set(database=name).render_as_string(hide_password=False)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    engine = create_engine(url)
    owner, profile, session = uuid4(), uuid4(), uuid4()
    active, edited, deleted = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    try:
        command.upgrade(config, "20261013_0016")
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO users (id,status,email,display_name) "
                    "VALUES (:id,'active','migration@example.test','Migration Learner')"
                ),
                {"id": owner},
            )
            db.execute(
                text(
                    "INSERT INTO language_profiles "
                    "(id,user_id,base_language_id,target_language_id,status) "
                    "VALUES (:id,:user,'english','mandarin','active')"
                ),
                {"id": profile, "user": owner},
            )
            db.execute(
                text(
                    "INSERT INTO sessions "
                    "(id,user_id,language_profile_id,creation_key_digest,state,row_version,"
                    "connected_limit_ms,connected_ms,created_at,updated_at) "
                    "VALUES (:id,:user,:profile,:digest,'ready',1,600000,0,:now,:now)"
                ),
                {"id": session, "user": owner, "profile": profile, "digest": "a" * 64, "now": now},
            )
            for entry, body, origin, version, removed, expiry in (
                (active, "Plays volleyball.", "capture", 1, None, now + timedelta(days=90)),
                (
                    edited,
                    "Plays indoor volleyball.",
                    "learner_edit",
                    2,
                    None,
                    now - timedelta(days=1),
                ),
                (deleted, None, "capture", 3, now, now + timedelta(days=90)),
            ):
                db.execute(
                    text(
                        "INSERT INTO learner_file_entries "
                        "(id,language_profile_id,source_session_id,kind,insight_topic,fact_digest,text,"
                        "origin,version,created_at,updated_at,expires_at,deleted_at) "
                        "VALUES (:id,:profile,:session,'insight','interest',:digest,:body,:origin,"
                        ":version,:now,:now,:expiry,:removed)"
                    ),
                    {
                        "id": entry,
                        "profile": profile,
                        "session": session,
                        "digest": str(entry).replace("-", "") * 2,
                        "body": body,
                        "origin": origin,
                        "version": version,
                        "now": now,
                        "expiry": expiry,
                        "removed": removed,
                    },
                )
        command.upgrade(config, "head")
        with engine.begin() as db:
            rows = db.execute(
                text(
                    "SELECT id,user_id,text,origin,version,deleted_at IS NOT NULL "
                    "FROM user_insights ORDER BY id"
                )
            ).all()
            assert {tuple(row) for row in rows} == {
                (active, owner, "Plays volleyball.", "capture", 1, False),
                (edited, owner, "Plays indoor volleyball.", "learner_edit", 2, False),
                (deleted, owner, None, "capture", 3, True),
            }
            assert (
                db.scalar(
                    text("SELECT COUNT(*) FROM user_insights WHERE legacy_fact_digest IS NOT NULL")
                )
                == 3
            )
            db.execute(
                text("UPDATE user_insights SET text=NULL,deleted_at=:now,version=2 WHERE id=:id"),
                {"id": active, "now": now},
            )
        command.downgrade(config, "20261013_0016")
        with engine.connect() as db:
            assert db.execute(
                text(
                    "SELECT text,version,deleted_at IS NOT NULL "
                    "FROM learner_file_entries WHERE id=:id"
                ),
                {"id": active},
            ).one() == (None, 2, True)
        command.upgrade(config, "head")
        with engine.connect() as db:
            assert db.execute(
                text("SELECT text,version,deleted_at IS NOT NULL FROM user_insights WHERE id=:id"),
                {"id": active},
            ).one() == (None, 2, True)
    finally:
        engine.dispose()
        with admin.connect() as db:
            db.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
