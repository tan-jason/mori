"""Deterministic selection and published-course integrity."""

from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from mori.modules.curriculum.catalog import (
    MANDARIN_COURSE,
    CodeCourseCatalog,
)
from mori.modules.curriculum.curriculum import FRAMEWORK_ID, LESSONS
from mori.modules.curriculum.domain import (
    CurriculumItem,
    PlanningContext,
    PublishedCourse,
    build_session_plan,
    validate_published_course,
)


def _course() -> PublishedCourse:
    def item(
        key: str,
        label: str,
        level: str,
        purpose: str,
        weight: int,
        topics: tuple[str, ...],
        words: tuple[str, ...],
        prerequisites: tuple[str, ...],
    ) -> CurriculumItem:
        return CurriculumItem(
            key=key,
            label=label,
            level=level,
            kind="conversation",
            purpose=purpose,
            selection_weight=weight,
            target_language_content="你好。",
            enabled=True,
            topic_tags=topics,
            word_tags=words,
            prerequisites=prerequisites,
        )

    items = (
        item("beginner-check", "Beginner diagnostic", "beginner", "diagnostic", 1, (), (), ()),
        item(
            "greetings",
            "Greet someone",
            "beginner",
            "skill",
            2,
            ("people",),
            ("hello",),
            ("beginner-check",),
        ),
        item(
            "daily-life",
            "Describe your day",
            "beginner",
            "skill",
            3,
            ("weekend",),
            ("today",),
            ("greetings",),
        ),
        item(
            "intermediate-check",
            "Intermediate diagnostic",
            "intermediate",
            "diagnostic",
            1,
            (),
            (),
            (),
        ),
        item(
            "past-event",
            "Tell a past event",
            "intermediate",
            "skill",
            2,
            ("weekend",),
            ("market",),
            ("intermediate-check",),
        ),
        item("advanced-check", "Advanced diagnostic", "advanced", "diagnostic", 1, (), (), ()),
    )
    return PublishedCourse(
        "english", "mandarin", "v1", "pair-v1", "voice-v1", "pair policy", "voice policy", items
    )


def test_first_session_uses_placement_diagnostic_and_practice_is_ungraded() -> None:
    course = _course()
    learning = build_session_plan(
        PlanningContext("learning", "intermediate", "my weekend", ("market",)), course
    )
    practice = build_session_plan(
        PlanningContext("practice", None, "my weekend", ("market",)), course
    )
    assert [(item.kind, item.curriculum_item_key) for item in learning] == [
        ("graded", "intermediate-check")
    ]
    assert practice[0].kind == "conversation_focus"
    assert practice[0].curriculum_item_key is None
    assert "my weekend" in practice[0].label


def test_placement_tie_break_is_independent_of_storage_order() -> None:
    course = _course()
    second = replace(
        course.items[3],
        key="intermediate-check-two",
        label="Second diagnostic",
    )
    context = PlanningContext("learning", "intermediate", None, ())
    forward = replace(course, items=(*course.items, second))
    reverse = replace(course, items=tuple(reversed(forward.items)))
    assert build_session_plan(context, forward) == build_session_plan(context, reverse)


def test_review_repair_and_requested_words_have_stable_order() -> None:
    course = _course()
    context = PlanningContext(
        "learning",
        "intermediate",
        "weekend",
        ("market",),
        mastered_keys=frozenset({"beginner-check", "greetings", "intermediate-check"}),
        due_keys=frozenset({"greetings"}),
        repair_keys=frozenset({"past-event"}),
    )
    planned = build_session_plan(context, course)
    assert [item.curriculum_item_key for item in planned] == [
        "past-event",
        "greetings",
        "daily-life",
    ]
    assert (
        build_session_plan(context, replace(course, items=tuple(reversed(course.items)))) == planned
    )


def test_prerequisites_and_cycles_fail_closed() -> None:
    course = _course()
    planned = build_session_plan(
        PlanningContext(
            "learning", "beginner", None, (), mastered_keys=frozenset({"beginner-check"})
        ),
        course,
    )
    assert [item.curriculum_item_key for item in planned] == ["greetings"]
    cyclic = replace(
        course, items=(replace(course.items[0], prerequisites=("greetings",)), *course.items[1:])
    )
    with pytest.raises(ValueError, match="cycle"):
        validate_published_course(cyclic)


def test_mastered_course_still_offers_review() -> None:
    course = _course()
    planned = build_session_plan(
        PlanningContext(
            "learning",
            "advanced",
            None,
            (),
            mastered_keys=frozenset(item.key for item in course.items),
        ),
        course,
    )
    assert planned
    assert all(item.kind == "graded" for item in planned)


@pytest.mark.asyncio
async def test_code_catalog_exposes_published_course() -> None:
    catalog = CodeCourseCatalog()
    pairs = await catalog.language_pairs()
    assert next(pair for pair in pairs if pair.target_language_id == "mandarin").available
    assert not next(pair for pair in pairs if pair.target_language_id == "spanish").available
    assert (
        await catalog.published_course(base_language_id="english", target_language_id="mandarin")
        is MANDARIN_COURSE
    )
    assert (
        await catalog.published_course(base_language_id="english", target_language_id="spanish")
        is None
    )
    validate_published_course(MANDARIN_COURSE)
    assert (
        catalog.course_version(
            base_language_id="english",
            target_language_id="mandarin",
            version=FRAMEWORK_ID,
        )
        is MANDARIN_COURSE
    )
    assert [item.key for item in MANDARIN_COURSE.items] == [lesson.key for lesson in LESSONS]


def test_shared_framework_selects_next_lesson_independent_of_language_level() -> None:
    first = build_session_plan(PlanningContext("learning", "advanced", None, ()), MANDARIN_COURSE)
    second = build_session_plan(
        PlanningContext(
            "learning", "beginner", None, (), mastered_keys=frozenset({LESSONS[0].key})
        ),
        MANDARIN_COURSE,
    )
    assert first[0].curriculum_item_key == LESSONS[0].key
    assert second[0].curriculum_item_key == LESSONS[1].key


def test_shared_course_tables_are_removed(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT to_regclass('public.course_catalog')")) is None
            assert connection.scalar(text("SELECT to_regclass('public.curriculum_items')")) is None
    finally:
        engine.dispose()


def test_upgrade_moves_selected_item_identity_to_key(database_url: str) -> None:
    database_name = f"mori_migration_{uuid4().hex}"
    admin = create_engine(database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    migration_url = (
        make_url(database_url).set(database=database_name).render_as_string(hide_password=False)
    )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", migration_url)
    engine = create_engine(migration_url)
    session_id = UUID(int=9001)
    try:
        command.upgrade(config, "20260929_0004")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, status, email, display_name) "
                    "VALUES (:id, 'active', 'migration@example.test', 'Migration Learner')"
                ),
                {"id": UUID(int=9002)},
            )
            connection.execute(
                text(
                    "INSERT INTO language_profiles "
                    "(id, user_id, base_language_id, target_language_id, status) "
                    "VALUES (:id, :user_id, 'english', 'mandarin', 'active')"
                ),
                {"id": UUID(int=9003), "user_id": UUID(int=9002)},
            )
            connection.execute(
                text(
                    "INSERT INTO sessions "
                    "(id, user_id, language_profile_id, creation_key_digest, state, "
                    "row_version, connected_limit_ms, connected_ms, created_at, updated_at) "
                    "VALUES (:id, :user_id, :profile_id, :digest, 'planned', "
                    "3, 1200000, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "id": session_id,
                    "user_id": UUID(int=9002),
                    "profile_id": UUID(int=9003),
                    "digest": "a" * 64,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO session_plans "
                    "(session_id, curriculum_version, selection_rule_version, prompt_version, "
                    "schema_version, mode, profile_version, preference_version, "
                    "settings_version, selected_level, requested_words, setup_digest, "
                    "curriculum_version_id, base_policy_version, pair_policy_version, "
                    "level_policy_version, objective_count, created_at) "
                    "VALUES (:id, 'mandarin-foundations-v1', 'selector-v1', 'base-v1', "
                    "'learning_plan_v1', 'learning', 1, 1, 1, 'beginner', '[]'::jsonb, "
                    ":digest, :version_id, 'base-v1', 'en-zh-pair-v1', 'beginner-v1', "
                    "1, CURRENT_TIMESTAMP)"
                ),
                {"id": session_id, "digest": "b" * 64, "version_id": UUID(int=100)},
            )
            connection.execute(
                text(
                    "INSERT INTO session_plan_objectives "
                    "(session_id, ordinal, text, kind, curriculum_item_id) "
                    "VALUES (:id, 1, 'Share a simple introduction and answer a follow-up.', "
                    "'graded', :item_id)"
                ),
                {"id": session_id, "item_id": UUID(int=101)},
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT p.curriculum_version, o.curriculum_item_key, o.text "
                    "FROM session_plans AS p JOIN session_plan_objectives AS o "
                    "ON o.session_id = p.session_id WHERE p.session_id = :id"
                ),
                {"id": session_id},
            ).one()
            assert tuple(row) == (
                "mandarin-foundations-v1",
                "beginner-check-in",
                "Share a simple introduction and answer a follow-up.",
            )
            assert connection.scalar(text("SELECT to_regclass('public.curriculum_items')")) is None
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        admin.dispose()
