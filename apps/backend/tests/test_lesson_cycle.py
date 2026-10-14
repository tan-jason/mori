"""Multi-session curriculum behavior and persistence with synthetic provider results."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_lesson_decisions import _answers, _decision
from test_realtime_webapp import _planned, _sql

from mori.modules.curriculum.curriculum import BEGINNER_LESSON_DEFINITIONS
from mori.modules.curriculum.planning import plan_learning_session
from mori.modules.curriculum.progress import (
    CriterionDistribution,
    LessonBenchmark,
    PracticeOccurrence,
    ProfileProgress,
    RecallItem,
    lesson_ready,
    recurring_help,
    usable_encounters,
)
from mori.modules.learning.application import AnalysisService
from mori.modules.learning.decisions import OpenAIDecisionsReviewer
from mori.modules.learning.domain import (
    FinalTurn,
    LearningCandidate,
    PracticeCandidate,
    UserInsightCandidate,
)
from mori.modules.learning.evidence import (
    AnalysisContext,
    CapabilityAttemptCandidate,
    EvidenceCandidate,
    IntroductionCandidate,
    ItemPracticeCandidate,
    LanguageItemCandidate,
)
from mori.modules.learning.models import LearningContributionModel
from mori.modules.learning.progress_store import load_learning_history, load_profile_progress
from mori.modules.sessions.models import SessionModel


def test_recurring_help_excludes_teaching_and_clears_after_independent_recall() -> None:
    profile, item, teaching = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    recall = RecallItem(
        item, profile, "我喜欢", "I like", "phrase", ("express-detail",), teaching, now
    )

    def occurrence(session: UUID, day: int, assistance: str) -> PracticeOccurrence:
        return PracticeOccurrence(
            uuid4(),
            session,
            now + timedelta(days=day),
            BEGINNER_LESSON_DEFINITIONS[0].lesson_key,
            "express-detail",
            item,
            assistance,
            True,
        )  # type: ignore[arg-type]

    first = occurrence(teaching, 0, "modelled")
    later = occurrence(uuid4(), 1, "cued")
    progress = ProfileProgress(profile, practices=(first, later), items=(recall,))
    assert recurring_help(progress) == (frozenset(), frozenset())
    assert usable_encounters(progress, first.lesson_key) == 2
    repeated = occurrence(later.session_id, 1, "modelled")
    assert (
        recurring_help(replace(progress, practices=(*progress.practices, repeated)))[0]
        == frozenset()
    )
    second = occurrence(uuid4(), 2, "cued")
    progress = replace(progress, practices=(*progress.practices, second))
    assert recurring_help(progress)[0] == {item}
    assert (
        plan_learning_session(progress, BEGINNER_LESSON_DEFINITIONS).new_item_allowance.maximum == 1
    )
    successful = occurrence(uuid4(), 3, "independent")
    assert recurring_help(replace(progress, practices=(*progress.practices, successful))) == (
        frozenset(),
        frozenset(),
    )


def test_readiness_requires_current_complete_criteria_and_explicit_configuration() -> None:
    definition = BEGINNER_LESSON_DEFINITIONS[0]
    assert definition.rubric
    scores = tuple(
        CriterionDistribution(c.key, True, (0, 0, 0, 1)) for c in definition.success_criteria
    )
    benchmark = LessonBenchmark(
        definition.lesson_key,
        definition.content_version,
        definition.rubric.version,
        2,
        scores,
        CriterionDistribution("lesson", True, (0, 0, 0, 1)),
    )
    progress = ProfileProgress(uuid4(), 2, benchmarks=(benchmark,))
    assert not lesson_ready(progress, definition, None)
    assert lesson_ready(progress, definition, 0.9)
    assert (
        plan_learning_session(
            progress, BEGINNER_LESSON_DEFINITIONS, probability_threshold=0.9
        ).lesson_key
        == BEGINNER_LESSON_DEFINITIONS[1].lesson_key
    )
    assert not lesson_ready(replace(progress, history_revision=3), definition, 0.9)
    for change in (
        replace(benchmark, complete=False),
        replace(benchmark, criteria=scores[:-1]),
        replace(benchmark, criteria=(replace(scores[0], assessable=False), *scores[1:])),
        replace(
            benchmark, criteria=(replace(scores[0], probabilities=(0, 0, 0.8, 0.2)), *scores[1:])
        ),
    ):
        assert not lesson_ready(replace(progress, benchmarks=(change,)), definition, 0.9)


class SyntheticExtractor:
    async def extract(
        self, *, mode: str, model: str, context: AnalysisContext, turns: tuple[FinalTurn, ...]
    ) -> LearningCandidate | PracticeCandidate:
        tutor, learner = turns[:2]
        evidence = EvidenceCandidate(learner.id, learner.text, tutor.id, tutor.text, "modelled")
        known = next((i for i in context.known_items if i.form == "我喜欢"), None)
        item = LanguageItemCandidate(
            "like",
            "我喜欢",
            "I like",
            "phrase",
            ("express-detail",),
            known_item_id=known.id if known else None,
            introduction=None if known else IntroductionCandidate(tutor.id, tutor.text),
        )
        return LearningCandidate(
            "Practiced expressing an interest.",
            (),
            (),
            language_items=(item,),
            item_practices=(ItemPracticeCandidate("like", evidence, "communicated", "production"),),
            capability_attempts=(
                CapabilityAttemptCandidate(
                    "express-detail", evidence, "communicated", "production", ("like",)
                ),
            ),
            user_insights=(
                UserInsightCandidate("Plays beach volleyball.", turns[2].id, turns[2].text),
            ),
        )


async def _finish(app: FastAPI, session_id: UUID) -> UUID:
    run_id = uuid4()
    async with app.state.session_maker() as db, db.begin():
        await db.execute(
            text("UPDATE usage_reservations SET state='consumed' WHERE session_id=:id"),
            {"id": session_id},
        )
        await db.execute(
            text(
                "UPDATE sessions SET state='analysis_pending', final_turn_sequence=3 WHERE id=:id"
            ),
            {"id": session_id},
        )
        for sequence, role, body in (
            (1, "tutor", "Say 我喜欢 to express what you like."),
            (2, "learner", "我喜欢排球。"),
            (3, "learner", "I play beach volleyball."),
        ):
            await db.execute(
                text(
                    "INSERT INTO session_turns "
                    "(id,session_id,provider_item_id,role,sequence,text,created_at) VALUES "
                    "(:id,:session,:provider,:role,:sequence,:body,:now)"
                ),
                {
                    "id": uuid4(),
                    "session": session_id,
                    "provider": f"item-{sequence}",
                    "role": role,
                    "sequence": sequence,
                    "body": body,
                    "now": datetime.now(UTC),
                },
            )
        await db.execute(
            text(
                "INSERT INTO analysis_runs "
                "(id,session_id,extractor_model,curriculum_version,mode,"
                "final_turn_sequence,status,created_at) "
                "SELECT "
                ":id,session_id,'synthetic',curriculum_version,mode,3,'pending',:now "
                "FROM session_plans WHERE session_id=:session"
            ),
            {"id": run_id, "session": session_id, "now": datetime.now(UTC)},
        )
    return run_id


def _reviewer(monkeypatch: pytest.MonkeyPatch) -> OpenAIDecisionsReviewer:
    reviewer = OpenAIDecisionsReviewer("synthetic-unused-key", probability_threshold=0.8)

    async def create(**kwargs: object):  # type: ignore[no-untyped-def]
        questions = kwargs["questions"]
        return _decision(_answers(questions))  # type: ignore[arg-type]

    monkeypatch.setattr(reviewer._client.decisions, "create", AsyncMock(side_effect=create))
    return reviewer


@pytest.mark.asyncio
async def test_capture_reanalysis_saved_recall_redaction_and_profile_isolation(
    client: TestClient, app: FastAPI, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, csrf = _planned(client)
    me = client.get("/api/v1/me").json()
    profile, owner = UUID(me["activeLanguageProfile"]["id"]), UUID(me["user"]["id"])
    reviewer = _reviewer(monkeypatch)
    service = AnalysisService(
        session_maker=app.state.session_maker,
        extractor=SyntheticExtractor(),
        decisions_reviewer=reviewer,
        fact_digest_key="synthetic-key",
    )
    first_run = await _finish(app, session_id)
    await service.process(first_run)
    await service.process(first_run)
    assert _sql(database_url, "SELECT history_revision FROM profile_learning_states") == [(1,)]
    assert _sql(database_url, "SELECT COUNT(*) FROM learning_contributions") == [(1,)]
    assert _sql(database_url, "SELECT COUNT(*) FROM user_insights") == [(1,)]
    async with app.state.session_maker() as db:
        progress = await load_profile_progress(db, profile)
        assert usable_encounters(progress, BEGINNER_LESSON_DEFINITIONS[0].lesson_key) == 1
        assert len(progress.items) == 1
        assert len((await load_learning_history(db, profile)).records) == 1
    next_session, _ = await app.state.session_service.create(
        user_id=owner, language_profile_id=profile, idempotency_key="cycle-next-session"
    )
    before = await app.state.session_service.load_realtime_config(
        user_id=owner, session_id=next_session.id
    )
    assert "我喜欢" in before.instructions
    assert "Plays beach volleyball." in before.instructions
    assert "Briefly welcome the learner back" in before.instructions
    assert before.source_history_revision == 1
    second_run = await _finish(app, next_session.id)
    await service.process(second_run)
    async with app.state.session_maker() as db:
        history = await load_learning_history(db, profile)
        assert len(history.records) == 2
        assert len(history.records[0].item_practices) == 1
    third, _ = await app.state.session_service.create(
        user_id=owner, language_profile_id=profile, idempotency_key="cycle-third-session"
    )
    entries = client.get(f"/api/v1/language-profiles/{profile}/learner-file").json()["entries"]
    assert len(entries) == 1
    headers = {"Origin": "http://web.test", "X-CSRF-Token": csrf, "If-Match": '"1"'}
    deleted = client.delete(
        f"/api/v1/language-profiles/{profile}/learner-file/{entries[0]['id']}", headers=headers
    )
    assert deleted.status_code == 204
    prepared = await app.state.session_service.prepare_call(
        user_id=owner, session_id=third.id, model_alias="synthetic", voice_alias="synthetic"
    )
    assert "我喜欢" not in prepared.instructions
    assert _sql(
        database_url,
        "SELECT jsonb_array_length(redacted_recall_item_ids) FROM session_prompt_builds",
    ) == [(1,)]
    async with app.state.session_maker() as db, db.begin():
        third_record = await db.get(SessionModel, third.id)
        assert third_record
        third_record.state = "ready"
        await db.execute(
            text(
                "INSERT INTO analysis_runs "
                "(id,session_id,extractor_model,curriculum_version,mode,"
                "final_turn_sequence,status,created_at) "
                "SELECT "
                ":id,session_id,'synthetic',curriculum_version,mode,3,'pending',:now "
                "FROM session_plans WHERE session_id=:session"
            ),
            {
                "id": (reanalysis := uuid4()),
                "session": next_session.id,
                "now": datetime.now(UTC) + timedelta(seconds=1),
            },
        )
    await service.process(reanalysis)
    await service.process(second_run)  # Superseded old jobs cannot replace the newer contribution.
    async with app.state.session_maker() as db:
        history = await load_learning_history(db, profile)
        assert all(not r.language_items and not r.item_practices for r in history.records)
        contribution = await db.get(LearningContributionModel, next_session.id)
        assert contribution and contribution.analysis_run_id == reanalysis
        other = uuid4()
        assert (await load_profile_progress(db, other)).items == ()
    assert len(client.get("/api/v1/user-insights").json()["entries"]) == 1
    french = client.post(
        "/api/v1/language-profiles",
        json={
            "baseLanguageId": "english",
            "targetLanguageId": "french",
            "startingChoice": "beginner",
            "learningGoal": "Travel",
            "speakingContext": "Everyday conversations",
        },
        headers={
            "Origin": "http://web.test",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "cycle-french-profile",
        },
    )
    assert french.status_code == 201
    french_id = UUID(french.json()["activeLanguageProfile"]["id"])
    async with app.state.session_maker() as db, db.begin():
        await db.execute(
            text("UPDATE usage_reservations SET state='consumed' WHERE session_id=:id"),
            {"id": third.id},
        )
    french_session, _ = await app.state.session_service.create(
        user_id=owner, language_profile_id=french_id, idempotency_key="cycle-french-session"
    )
    french_prompt = await app.state.session_service.load_realtime_config(
        user_id=owner, session_id=french_session.id
    )
    assert "Plays beach volleyball." in french_prompt.instructions
    assert "我喜欢" not in french_prompt.instructions
    assert french_prompt.source_history_revision == 0
    assert client.get(f"/api/v1/language-profiles/{french_id}/learner-file").json()["entries"] == []
    insight = client.get("/api/v1/user-insights").json()["entries"][0]
    edited = client.patch(
        f"/api/v1/user-insights/{insight['id']}",
        json={"text": "Plays indoor volleyball."},
        headers=headers,
    )
    assert edited.status_code == 200
    assert (
        client.delete(
            f"/api/v1/user-insights/{insight['id']}", headers={**headers, "If-Match": '"2"'}
        ).status_code
        == 204
    )
    # A repeated extraction cannot recreate a deleted user-owned fact.
    async with app.state.session_maker() as db, db.begin():
        await db.execute(
            text(
                "INSERT INTO analysis_runs "
                "(id,session_id,extractor_model,curriculum_version,mode,"
                "final_turn_sequence,status,created_at) "
                "SELECT "
                ":id,session_id,'synthetic',curriculum_version,mode,3,'pending',:now "
                "FROM session_plans WHERE session_id=:session"
            ),
            {
                "id": (last_run := uuid4()),
                "session": next_session.id,
                "now": datetime.now(UTC) + timedelta(seconds=2),
            },
        )
    await service.process(last_run)
    assert client.get("/api/v1/user-insights").json()["entries"] == []


@pytest.mark.asyncio
async def test_original_reviewed_legacy_quotes_remain_in_complete_history(
    client: TestClient,
    app: FastAPI,
) -> None:
    from test_realtime_webapp import FakeExtractor

    session, _ = _planned(client)
    me = client.get("/api/v1/me").json()
    profile = UUID(me["activeLanguageProfile"]["id"])
    run = await _finish(app, session)
    # This legacy fixture's accepted greeting has exact quotes and reviewer provenance.
    async with app.state.session_maker() as db, db.begin():
        await db.execute(
            text(
                "UPDATE session_turns SET text='你好' WHERE session_id=:session AND role='learner'"
            ),
            {"session": session},
        )
        await db.execute(
            text("UPDATE analysis_runs SET extractor_model='test-extractor' WHERE id=:run"),
            {"run": run},
        )
    await AnalysisService(
        session_maker=app.state.session_maker,
        extractor=FakeExtractor(),
        fact_digest_key="synthetic",
    ).process(run)
    async with app.state.session_maker() as db, db.begin():
        await db.execute(
            text("DELETE FROM learning_contributions WHERE session_id=:id"), {"id": session}
        )
    async with app.state.session_maker() as db:
        history = await load_learning_history(db, profile)
        assert len(history.records) == 1
        assert history.records[0].observations[0].evidence[0].learner.quote == "你好"
        assert history.complete


@pytest.mark.asyncio
async def test_history_change_during_benchmark_is_refreshed_before_becoming_current(
    client: TestClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, csrf = _planned(client)
    me = client.get("/api/v1/me").json()
    owner, profile = UUID(me["user"]["id"]), UUID(me["activeLanguageProfile"]["id"])
    reviewer = _reviewer(monkeypatch)
    service = AnalysisService(
        session_maker=app.state.session_maker,
        extractor=SyntheticExtractor(),
        decisions_reviewer=reviewer,
        fact_digest_key="synthetic",
    )
    await service.process(await _finish(app, session))
    next_session, _ = await app.state.session_service.create(
        user_id=owner, language_profile_id=profile, idempotency_key="race-next-session"
    )
    entry = client.get(f"/api/v1/language-profiles/{profile}/learner-file").json()["entries"][0]
    original = reviewer.benchmark
    calls = 0

    async def changing_history(**kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        result = await original(**kwargs)  # type: ignore[arg-type]
        if calls == 1:
            assert (
                client.delete(
                    f"/api/v1/language-profiles/{profile}/learner-file/{entry['id']}",
                    headers={"Origin": "http://web.test", "X-CSRF-Token": csrf, "If-Match": '"1"'},
                ).status_code
                == 204
            )
        return result

    monkeypatch.setattr(reviewer, "benchmark", changing_history)
    await service.process(await _finish(app, next_session.id))
    assert calls == 2
    async with app.state.session_maker() as db:
        progress = await load_profile_progress(db, profile)
        history = await load_learning_history(db, profile)
        assert progress.history_revision == 3
        assert progress.benchmarks[-1].history_revision == progress.history_revision
        assert progress.benchmarks[-2].history_revision != progress.history_revision
        assert all(not record.item_practices for record in history.records)
