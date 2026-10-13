"""WebRTC API to durable session lifecycle without a provider network call."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from mori.modules.learning.application import AnalysisService
from mori.modules.learning.domain import (
    CorrectionCandidate,
    FinalTurn,
    InsightCandidate,
    LearningCandidate,
    ObservationCandidate,
    PracticeCandidate,
)
from mori.modules.learning.evidence import (
    AcceptedObservation,
    AnalysisContext,
    EvidenceCandidate,
    ObservationReview,
    ReviewDecision,
)
from mori.modules.learning.queue import enqueue_capture
from mori.modules.sessions.application import SessionService
from mori.modules.sessions.realtime_provider import CreatedCall
from mori.modules.sessions.supervisor import RealtimeSupervisor


class FakeProvider:
    def __init__(self) -> None:
        self.hung_up: list[str] = []

    async def create_call(self, **_kwargs: str) -> CreatedCall:
        return CreatedCall(call_id="rtc_test_call", answer_sdp="v=0\r\nanswer")

    async def hangup(self, call_id: str) -> None:
        self.hung_up.append(call_id)


class FakeExtractor:
    async def extract(
        self, *, mode: str, model: str, context: AnalysisContext, turns: tuple[FinalTurn, ...]
    ) -> LearningCandidate | PracticeCandidate:
        assert mode == "learning" and model == "test-extractor" and context.lesson
        learner_id = next(turn.id for turn in turns if turn.role == "learner")
        return LearningCandidate(
            summary="You practiced a short greeting.",
            observations=(
                ObservationCandidate(
                    "use",
                    "You greeted Mori.",
                    0.9,
                    context.lesson.key,
                    (EvidenceCandidate(learner_id, "你好", None, None, "independent"),),
                ),
            ),
            corrections=(CorrectionCandidate(learner_id, "你好"),),
        )

    async def review_observations(
        self,
        *,
        model: str,
        context: AnalysisContext,
        turns: tuple[FinalTurn, ...],
        observations: tuple[AcceptedObservation, ...],
    ) -> tuple[ObservationReview, ...]:
        return tuple(
            ObservationReview(ordinal, "supported", "The learner used a target-language greeting.")
            for ordinal, _ in enumerate(observations, 1)
        )


class FakeInsightExtractor(FakeExtractor):
    async def extract(
        self, *, mode: str, model: str, context: AnalysisContext, turns: tuple[FinalTurn, ...]
    ) -> LearningCandidate | PracticeCandidate:
        assert mode == "learning"
        learner = next(turn for turn in turns if turn.role == "learner")
        return LearningCandidate(
            "You discussed food.",
            (),
            (),
            (
                InsightCandidate("cooking", learner.id, "I like cooking", "interest", 0.9),
                InsightCandidate(
                    "hiking", learner.id, "I like cooking and hiking", "interest", 0.9
                ),
            ),
        )


def _planned(client: TestClient, *, starting_choice: str = "beginner") -> tuple[UUID, str]:
    start = client.get("/auth/google/start")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    callback = client.get("/auth/google/callback", params={"state": state, "code": "valid-code"})
    assert callback.status_code == 302
    csrf = client.get("/api/v1/me").json()["csrfToken"]
    headers = {
        "Origin": "http://web.test",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": "profile-realtime-webapp",
    }
    profile = client.post(
        "/api/v1/language-profiles",
        json={
            "baseLanguageId": "english",
            "targetLanguageId": "mandarin",
            "startingChoice": starting_choice,
            "learningGoal": "Talk with family",
            "speakingContext": "Casual conversations with relatives",
        },
        headers=headers,
    )
    assert profile.status_code == 201
    session = client.post(
        "/api/v1/sessions",
        json={"languageProfileId": profile.json()["activeLanguageProfile"]["id"]},
        headers={**headers, "Idempotency-Key": "session-realtime-webapp"},
    )
    assert session.status_code == 201
    return UUID(session.json()["id"]), csrf


def _sql(database_url: str, query: str) -> list[tuple[object, ...]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as db:
            return [tuple(row) for row in db.execute(text(query)).all()]
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["unsupported", "uncertain", "missing", "failed"])
async def test_evidence_review_gates_persistence_and_failed_review_can_retry(
    client: TestClient, app: FastAPI, database_url: str, decision: str
) -> None:
    session_id, _ = _planned(client)
    now = datetime.now(UTC)
    run_id = uuid4()
    async with app.state.session_maker() as db, db.begin():
        await db.execute(
            text(
                "UPDATE sessions SET state='analysis_pending', final_turn_sequence=1 WHERE id=:id"
            ),
            {"id": session_id},
        )
        await db.execute(
            text(
                "INSERT INTO session_turns "
                "(id, session_id, provider_item_id, role, sequence, text, created_at) "
                "VALUES (:id, :session_id, 'review-test', 'learner', 1, '你好', :now)"
            ),
            {"id": uuid4(), "session_id": session_id, "now": now},
        )
        await db.execute(
            text(
                "INSERT INTO analysis_runs "
                "(id, session_id, extractor_model, curriculum_version, mode, final_turn_sequence, "
                "status, created_at) SELECT :id, session_id, 'test-extractor', curriculum_version, "
                "mode, 1, 'pending', :now FROM session_plans WHERE session_id=:session_id"
            ),
            {"id": run_id, "session_id": session_id, "now": now},
        )

    class Reviewer(FakeExtractor):
        async def review_observations(
            self,
            *,
            model: str,
            context: AnalysisContext,
            turns: tuple[FinalTurn, ...],
            observations: tuple[AcceptedObservation, ...],
        ) -> tuple[ObservationReview, ...]:
            if decision == "failed":
                raise RuntimeError("review provider unavailable")
            if decision == "missing":
                return ()
            verdict: ReviewDecision = "unsupported" if decision == "unsupported" else "uncertain"
            return (ObservationReview(1, verdict, "The claim is not established."),)

    analysis = AnalysisService(
        session_maker=app.state.session_maker,
        extractor=Reviewer(),
        fact_digest_key="test-key",
    )
    if decision in {"failed", "missing"}:
        with pytest.raises((RuntimeError, ValueError)):
            await analysis.process(run_id)
        assert _sql(database_url, "SELECT state FROM sessions") == [("analysis_failed",)]
        assert _sql(database_url, "SELECT count(*) FROM recaps") == [(0,)]
    else:
        await analysis.process(run_id)
        await analysis.process(run_id)
        assert _sql(database_url, "SELECT state FROM sessions") == [("ready",)]
        assert _sql(database_url, "SELECT count(*) FROM recaps") == [(1,)]
        recap = client.get(f"/api/v1/sessions/{session_id}/recap").json()
        assert recap["status"] == "ready"
        assert recap["observations"] == []
    assert _sql(database_url, "SELECT count(*) FROM analysis_observations") == [(0,)]
    assert _sql(database_url, "SELECT count(*) FROM learner_file_entries") == [(0,)]
    if decision in {"failed", "missing"}:
        retry = AnalysisService(
            session_maker=app.state.session_maker,
            extractor=FakeExtractor(),
            fact_digest_key="test-key",
        )
        await retry.process(run_id)
        await retry.process(run_id)
        assert _sql(database_url, "SELECT state FROM sessions") == [("ready",)]
        assert _sql(database_url, "SELECT count(*) FROM analysis_observations") == [(1,)]
        assert _sql(database_url, "SELECT count(*) FROM recaps") == [(1,)]


@pytest.mark.asyncio
async def test_analysis_job_rolls_back_with_its_session_transaction(
    app: FastAPI, database_url: str
) -> None:
    before = _sql(database_url, "SELECT count(*) FROM procrastinate_jobs")
    with pytest.raises(RuntimeError, match="rollback"):
        async with app.state.session_maker() as db, db.begin():
            await enqueue_capture(db, uuid4())
            raise RuntimeError("rollback")
    assert _sql(database_url, "SELECT count(*) FROM procrastinate_jobs") == before


def test_learner_file_pages_all_captured_entries(client: TestClient, database_url: str) -> None:
    session_id, _ = _planned(client)
    profile_id = client.get("/api/v1/me").json()["activeLanguageProfile"]["id"]
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            for index in range(51):
                db.execute(
                    text(
                        "INSERT INTO learner_file_entries "
                        "(id, language_profile_id, source_session_id, kind, text, origin, "
                        "version, created_at, updated_at) "
                        "VALUES (:id, :profile_id, :session_id, 'learning', :text, 'capture', "
                        "1, :created_at, :created_at)"
                    ),
                    {
                        "id": uuid4(),
                        "profile_id": UUID(profile_id),
                        "session_id": session_id,
                        "text": f"Learning {index}",
                        "created_at": datetime.now(UTC) - timedelta(minutes=index),
                    },
                )
    finally:
        engine.dispose()
    path = f"/api/v1/language-profiles/{profile_id}/learner-file"
    first = client.get(path)
    assert first.status_code == 200
    assert len(first.json()["entries"]) == 50
    cursor = first.json()["nextCursor"]
    assert cursor
    second = client.get(path, params={"cursor": cursor})
    assert second.status_code == 200
    assert [entry["text"] for entry in second.json()["entries"]] == ["Learning 50"]
    assert second.json()["nextCursor"] is None
    assert client.get(path, params={"cursor": "invalid"}).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("starting_choice", ["beginner", "fluent"])
async def test_future_prompt_keeps_insights_when_learnings_fill_the_file(
    client: TestClient, app: FastAPI, database_url: str, starting_choice: str
) -> None:
    session_id, _ = _planned(client, starting_choice=starting_choice)
    me = client.get("/api/v1/me").json()
    profile_id = UUID(me["activeLanguageProfile"]["id"])
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            for index in range(9):
                db.execute(
                    text(
                        "INSERT INTO learner_file_entries "
                        "(id, language_profile_id, source_session_id, kind, text, origin, "
                        "version, created_at, updated_at) "
                        "VALUES (:id, :profile_id, :session_id, 'learning', :body, 'capture', "
                        "1, :now, :now)"
                    ),
                    {
                        "id": uuid4(),
                        "profile_id": profile_id,
                        "session_id": session_id,
                        "body": f"Practiced structure {index}.",
                        "now": datetime.now(UTC) + timedelta(seconds=index),
                    },
                )
            db.execute(
                text(
                    "INSERT INTO learner_file_entries "
                    "(id, language_profile_id, source_session_id, kind, insight_topic, text, "
                    "origin, version, created_at, updated_at, expires_at) "
                    "VALUES (:id, :profile_id, :session_id, 'insight', 'interest', "
                    "'Enjoys playing beach volleyball.', 'capture', 1, :now, :now, :expiry)"
                ),
                {
                    "id": uuid4(),
                    "profile_id": profile_id,
                    "session_id": session_id,
                    "now": datetime.now(UTC) - timedelta(days=1),
                    "expiry": datetime.now(UTC) + timedelta(days=89),
                },
            )
    finally:
        engine.dispose()
    prompt = await SessionService(session_maker=app.state.session_maker).load_realtime_config(
        user_id=UUID(me["user"]["id"]), session_id=session_id
    )
    assert "Enjoys playing beach volleyball." in prompt.instructions
    assert "Practiced structure 0." not in prompt.instructions
    if starting_choice == "beginner":
        assert "Practiced structure 8." in prompt.instructions
    else:
        assert "Practiced structure" not in prompt.instructions


@pytest.mark.asyncio
async def test_capturer_saves_expiring_insight_and_delete_revokes_it(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    session_id, csrf = _planned(client)
    profile_id = client.get("/api/v1/me").json()["activeLanguageProfile"]["id"]
    turn_id, run_id = uuid4(), uuid4()
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            plan = db.execute(
                text("SELECT curriculum_version, mode FROM session_plans WHERE session_id=:id"),
                {"id": session_id},
            ).one()
            db.execute(
                text(
                    "UPDATE sessions SET state='analysis_pending', "
                    "final_turn_sequence=1 WHERE id=:id"
                ),
                {"id": session_id},
            )
            db.execute(
                text(
                    "INSERT INTO session_turns "
                    "(id, session_id, provider_item_id, role, sequence, text, created_at) "
                    "VALUES (:id, :session_id, 'test-item', 'learner', 1, "
                    "'I like cooking and hiking', :now)"
                ),
                {"id": turn_id, "session_id": session_id, "now": datetime.now(UTC)},
            )
            db.execute(
                text(
                    "INSERT INTO analysis_runs "
                    "(id, session_id, extractor_model, "
                    "curriculum_version, mode, final_turn_sequence, status, created_at) "
                    "VALUES (:id, :session_id, 'test-extractor', "
                    ":curriculum, :mode, 1, 'pending', :now)"
                ),
                {
                    "id": run_id,
                    "session_id": session_id,
                    "curriculum": plan.curriculum_version,
                    "mode": plan.mode,
                    "now": datetime.now(UTC),
                },
            )
    finally:
        engine.dispose()
    await AnalysisService(
        session_maker=app.state.session_maker,
        extractor=FakeInsightExtractor(),
        fact_digest_key="test-secret-key",
    ).process(run_id)
    path = f"/api/v1/language-profiles/{profile_id}/learner-file"
    entries = client.get(path).json()["entries"]
    assert len(entries) == 2
    assert {entry["text"] for entry in entries} == {"Enjoys cooking.", "Enjoys hiking."}
    assert all(entry["kind"] == "insight" for entry in entries)
    assert all(
        datetime.fromisoformat(entry["expiresAt"]) > datetime.now(UTC) + timedelta(days=89)
        for entry in entries
    )
    cooking = next(entry for entry in entries if entry["text"] == "Enjoys cooking.")
    deleted = client.delete(
        f"{path}/{cooking['id']}",
        headers={"Origin": "http://web.test", "X-CSRF-Token": csrf, "If-Match": '"1"'},
    )
    assert deleted.status_code == 204
    assert [entry["text"] for entry in client.get(path).json()["entries"]] == ["Enjoys hiking."]
    rows = _sql(database_url, "SELECT text, deleted_at IS NOT NULL FROM learner_file_entries")
    assert set(rows) == {
        (None, True),
        ("Enjoys hiking.", False),
    }


@pytest.mark.asyncio
async def test_webapp_call_consumes_once_and_supervisor_finishes(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    session_id, csrf = _planned(client)
    provider = FakeProvider()
    app.state.realtime_provider = provider
    app.state.realtime_supervisor = SimpleNamespace(healthy=True)
    app.state.settings.openai_safety_id_secret = SecretStr("test-safety-id-secret")
    headers = {"Origin": "http://web.test", "X-CSRF-Token": csrf}
    availability = client.get("/api/v1/sessions/availability")
    assert availability.json() == {"available": True, "maxCallSeconds": 600}
    denied = client.post(
        f"/api/v1/sessions/{session_id}/webrtc",
        content="v=0\r\noffer",
        headers={"Content-Type": "application/sdp"},
    )
    assert denied.status_code == 403
    exchange = client.post(
        f"/api/v1/sessions/{session_id}/webrtc",
        content="v=0\r\noffer",
        headers={**headers, "Content-Type": "application/sdp"},
    )
    assert exchange.status_code == 200
    assert exchange.text == "v=0\r\nanswer"
    attempt_id = UUID(exchange.headers["X-Call-Attempt-ID"])
    stored = _sql(
        database_url,
        "SELECT state, provider_call_id, hard_deadline_at, client_ack_deadline_at "
        "FROM session_call_attempts",
    )[0]
    assert stored[0:2] == ("awaiting_client", "rtc_test_call")
    assert isinstance(stored[2], datetime) and stored[2] > datetime.now(UTC)
    assert 580 < (stored[2] - datetime.now(UTC)).total_seconds() <= 600
    assert isinstance(stored[3], datetime) and stored[3] < stored[2]
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/webrtc",
            content="v=0\r\noffer",
            headers={**headers, "Content-Type": "application/sdp"},
        ).status_code
        == 409
    )
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            db.execute(
                text("UPDATE session_call_attempts SET sideband_ready_at=:ready"),
                {"ready": datetime.now(UTC)},
            )
    finally:
        engine.dispose()
    ack_path = f"/api/v1/sessions/{session_id}/connections/{attempt_id}/ack"
    assert client.post(ack_path, headers=headers).status_code == 204
    assert client.post(ack_path, headers=headers).status_code == 204
    service: SessionService = app.state.session_service
    supervisor = RealtimeSupervisor(
        session_maker=app.state.session_maker,
        service=service,
        provider=provider,  # type: ignore[arg-type]
        api_key="unused",
        extractor_model="test-extractor",
    )
    for item_id, role in (("item_1", "user"), ("item_2", "assistant")):
        await supervisor._event(
            attempt_id,
            json.dumps({"type": "conversation.item.added", "item": {"id": item_id, "role": role}}),
        )
    await supervisor._event(
        attempt_id,
        json.dumps(
            {
                "type": "response.output_audio_transcript.done",
                "item_id": "item_2",
                "transcript": "你好！",
            }
        ),
    )
    for transcript in ("你好", "duplicate"):
        await supervisor._event(
            attempt_id,
            json.dumps(
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "item_id": "item_1",
                    "transcript": transcript,
                }
            ),
        )
    assert _sql(database_url, "SELECT sequence, text FROM session_turns ORDER BY sequence") == [
        (1, "你好"),
        (2, "你好！"),
    ]
    assert _sql(database_url, "SELECT state FROM usage_reservations") == [("consumed",)]
    profile_id = client.get("/api/v1/me").json()["activeLanguageProfile"]["id"]
    next_session_headers = {**headers, "Idempotency-Key": "next-session-realtime-webapp"}
    overlapping = client.post(
        "/api/v1/sessions",
        json={"languageProfileId": profile_id},
        headers=next_session_headers,
    )
    assert overlapping.status_code == 409
    assert overlapping.json()["error"]["code"] == "voice_entitlement_unavailable"
    assert client.post(f"/api/v1/sessions/{session_id}/end", headers=headers).status_code == 204
    await supervisor._scan()
    for _ in range(100):
        if _sql(database_url, "SELECT state FROM session_call_attempts") == [("ended",)]:
            break
        await asyncio.sleep(0.01)
    await supervisor.stop()
    assert provider.hung_up == ["rtc_test_call"]
    assert _sql(database_url, "SELECT state, final_turn_sequence FROM sessions") == [
        ("analysis_pending", 2)
    ]
    assert _sql(database_url, "SELECT state FROM usage_reservations") == [("consumed",)]
    run_id = _sql(database_url, "SELECT id FROM analysis_runs")[0][0]
    assert isinstance(run_id, UUID)
    assert _sql(database_url, "SELECT status FROM procrastinate_jobs") == [("todo",)]
    assert client.get(f"/api/v1/sessions/{session_id}/recap").json() == {
        "mode": "learning",
        "status": "processing",
    }
    analysis = AnalysisService(
        session_maker=app.state.session_maker,
        extractor=FakeExtractor(),
        fact_digest_key="test-secret-key",
    )
    await analysis.process(run_id)
    await analysis.process(run_id)
    ready = client.get(f"/api/v1/sessions/{session_id}/recap")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["summary"] == "You practiced a short greeting."
    assert ready.json()["observations"][0]["detail"] == "You greeted Mori."
    assert _sql(database_url, "SELECT count(*) FROM recaps") == [(1,)]
    assert _sql(database_url, "SELECT count(*) FROM analysis_observations") == [(1,)]
    assert _sql(
        database_url,
        "SELECT curriculum_item_key, review_status, review_reason IS NOT NULL "
        "FROM analysis_observations",
    ) == [("lesson-01-introduction", "supported", True)]
    assert _sql(
        database_url,
        "SELECT learner_quote, learner_quote_start, learner_quote_end, assistance, "
        "opportunity_turn_id FROM analysis_observation_turns",
    ) == [("你好", 0, 2, "independent", None)]
    file_path = f"/api/v1/language-profiles/{profile_id}/learner-file"
    entries = client.get(file_path)
    assert entries.status_code == 200
    assert len(entries.json()["entries"]) == 1
    entry = entries.json()["entries"][0]
    assert entry["kind"] == "learning"
    assert entry["text"] == "You greeted Mori."
    assert client.post(file_path, json={"text": "Manual entry"}, headers=headers).status_code == 405
    app.state.session_service = SessionService(session_maker=app.state.session_maker)
    try:
        restricted = client.post(
            "/api/v1/sessions",
            json={"languageProfileId": profile_id},
            headers=next_session_headers,
        )
        assert restricted.status_code == 409
        assert restricted.json()["error"]["code"] == "voice_session_limit_reached"
        assert restricted.json()["error"]["message"] == (
            "You've reached your plan's limit of 1 session in total."
        )
    finally:
        app.state.session_service = service
    repeated = client.post(
        "/api/v1/sessions",
        json={"languageProfileId": profile_id},
        headers=next_session_headers,
    )
    assert repeated.status_code == 201
    entry_path = f"{file_path}/{entry['id']}"
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            db.execute(
                text("UPDATE sessions SET state='active' WHERE id=:id"),
                {"id": UUID(repeated.json()["id"])},
            )
        blocked = client.patch(
            entry_path,
            json={"text": "Changed during call"},
            headers={**headers, "If-Match": '"1"'},
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "learner_file_call_active"
        with engine.begin() as db:
            db.execute(
                text("UPDATE sessions SET state='planned' WHERE id=:id"),
                {"id": UUID(repeated.json()["id"])},
            )
    finally:
        engine.dispose()
    edit = client.patch(
        entry_path,
        json={"text": "  I practiced a greeting.  "},
        headers={**headers, "If-Match": '"1"'},
    )
    assert edit.status_code == 200
    assert edit.json()["text"] == "I practiced a greeting."
    assert edit.json()["version"] == 2
    assert _sql(database_url, "SELECT learner_quote FROM analysis_observation_turns") == [("你好",)]
    assert (
        client.patch(
            entry_path,
            json={"text": "stale"},
            headers={**headers, "If-Match": '"1"'},
        ).status_code
        == 412
    )
    prompt = await service.load_realtime_config(
        user_id=UUID(client.get("/api/v1/me").json()["user"]["id"]),
        session_id=UUID(repeated.json()["id"]),
    )
    assert "I practiced a greeting." in prompt.instructions
    deleted = client.delete(entry_path, headers={**headers, "If-Match": '"2"'})
    assert deleted.status_code == 204
    assert client.delete(entry_path, headers={**headers, "If-Match": '"2"'}).status_code == 204
    assert client.get(file_path).json()["entries"] == []
    prompt_after_delete = await service.load_realtime_config(
        user_id=UUID(client.get("/api/v1/me").json()["user"]["id"]),
        session_id=UUID(repeated.json()["id"]),
    )
    assert "I practiced a greeting." not in prompt_after_delete.instructions
    assert sorted(_sql(database_url, "SELECT state FROM usage_reservations")) == [
        ("consumed",),
        ("reserved",),
    ]


@pytest.mark.asyncio
async def test_expired_lease_can_be_taken_over_and_releases_unused_grant(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    session_id, csrf = _planned(client)
    provider = FakeProvider()
    app.state.realtime_provider = provider
    app.state.realtime_supervisor = SimpleNamespace(healthy=True)
    app.state.settings.openai_safety_id_secret = SecretStr("test-safety-id-secret")
    headers = {"Origin": "http://web.test", "X-CSRF-Token": csrf, "Content-Type": "application/sdp"}
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/webrtc", content="v=0\r\noffer", headers=headers
        ).status_code
        == 200
    )
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            db.execute(
                text(
                    "UPDATE session_call_attempts SET lease_owner=:owner, lease_until=:expired, "
                    "client_ack_deadline_at=:expired"
                ),
                {"owner": uuid4(), "expired": datetime.now(UTC) - timedelta(seconds=1)},
            )
    finally:
        engine.dispose()
    supervisor = RealtimeSupervisor(
        session_maker=app.state.session_maker,
        service=app.state.session_service,
        provider=provider,  # type: ignore[arg-type]
        api_key="unused",
    )
    await supervisor._scan()
    for _ in range(100):
        if _sql(database_url, "SELECT state FROM session_call_attempts") == [("ended",)]:
            break
        await asyncio.sleep(0.01)
    await supervisor.stop()
    assert provider.hung_up == ["rtc_test_call"]
    assert _sql(database_url, "SELECT state FROM sessions") == [("setup_failed",)]
    assert _sql(database_url, "SELECT state FROM usage_reservations") == [("released",)]


@pytest.mark.asyncio
async def test_takeover_marks_active_transcript_incomplete(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    session_id, csrf = _planned(client)
    provider = FakeProvider()
    app.state.realtime_provider = provider
    app.state.realtime_supervisor = SimpleNamespace(healthy=True)
    app.state.settings.openai_safety_id_secret = SecretStr("test-safety-id-secret")
    headers = {"Origin": "http://web.test", "X-CSRF-Token": csrf}
    exchange = client.post(
        f"/api/v1/sessions/{session_id}/webrtc",
        content="v=0\r\noffer",
        headers={**headers, "Content-Type": "application/sdp"},
    )
    assert exchange.status_code == 200
    attempt_id = UUID(exchange.headers["X-Call-Attempt-ID"])
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            db.execute(
                text("UPDATE session_call_attempts SET sideband_ready_at=:ready"),
                {"ready": datetime.now(UTC)},
            )
    finally:
        engine.dispose()
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/connections/{attempt_id}/ack", headers=headers
        ).status_code
        == 204
    )
    await app.state.session_service.record_turn(
        attempt_id=attempt_id, provider_item_id="learner_1", role="learner", text="你好"
    )
    engine = create_engine(database_url)
    try:
        with engine.begin() as db:
            db.execute(
                text(
                    "UPDATE session_call_attempts SET lease_owner=:owner, lease_until=:expired, "
                    "end_requested_at=:requested"
                ),
                {
                    "owner": uuid4(),
                    "expired": datetime.now(UTC) - timedelta(seconds=1),
                    "requested": datetime.now(UTC),
                },
            )
    finally:
        engine.dispose()
    supervisor = RealtimeSupervisor(
        session_maker=app.state.session_maker,
        service=app.state.session_service,
        provider=provider,  # type: ignore[arg-type]
        api_key="unused",
    )
    await supervisor._scan()
    for _ in range(100):
        if _sql(database_url, "SELECT state FROM session_call_attempts") == [("ended",)]:
            break
        await asyncio.sleep(0.01)
    await supervisor.stop()
    assert _sql(database_url, "SELECT state FROM sessions") == [("analysis_failed",)]
    assert _sql(database_url, "SELECT transcript_gap FROM session_call_attempts") == [(True,)]
