"""Session reservation, idempotency, and ownership against PostgreSQL."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

import mori.modules.sessions.application as session_application
from mori.modules.learner_profiles.domain import (
    CorrectionPreference,
    CreateProfile,
    StartingChoice,
    TutorPace,
)
from mori.modules.sessions.application import SessionService
from mori.modules.sessions.errors import (
    SessionNotConnectable,
    SessionNotFound,
    VoiceEntitlementUnavailable,
)


def _sign_in(client: TestClient, choice: str = "beginner") -> tuple[str, str]:
    start = client.get("/auth/google/start")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    assert (
        client.get(
            "/auth/google/callback", params={"state": state, "code": "valid-code"}
        ).status_code
        == 302
    )
    me = client.get("/api/v1/me").json()
    response = client.post(
        "/api/v1/language-profiles",
        json={
            "baseLanguageId": "english",
            "targetLanguageId": "mandarin",
            "startingChoice": choice,
            "learningGoal": "Talk with family",
            "speakingContext": "Casual conversations with relatives",
        },
        headers={
            "Origin": "http://web.test",
            "X-CSRF-Token": me["csrfToken"],
            "Idempotency-Key": "profile-setup-123",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["activeLanguageProfile"]["id"], me["csrfToken"]


def _create(client: TestClient, profile_id: str, csrf: str, key: str = "new-session-123"):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/sessions",
        json={"languageProfileId": profile_id},
        headers={
            "Origin": "http://web.test",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": key,
        },
    )


def _rows(database_url: str, query: str) -> list[tuple[object, ...]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(query)).all()]
    finally:
        engine.dispose()


def test_create_replay_and_competing_key(client: TestClient, database_url: str) -> None:
    profile_id, csrf = _sign_in(client)

    created = _create(client, profile_id, csrf)
    replay = _create(client, profile_id, csrf)
    competing = _create(client, profile_id, csrf, key="another-session-123")
    conflicting_replay = _create(client, str(uuid4()), csrf)

    assert created.status_code == 201
    assert replay.status_code == 200
    assert replay.json() == created.json()
    assert created.headers["location"] == f"/api/v1/sessions/{created.json()['id']}"
    assert created.json()["state"] == "planned"
    assert created.json()["rowVersion"] == 3
    assert created.json()["connectedLimitMs"] == 600_000
    assert competing.status_code == 409
    assert competing.json()["error"]["code"] == "voice_entitlement_unavailable"
    assert conflicting_replay.status_code == 409
    assert conflicting_replay.json()["error"]["code"] == "idempotency_conflict"
    assert _rows(database_url, "SELECT state FROM usage_reservations") == [("reserved",)]
    assert _rows(database_url, "SELECT kind FROM usage_events") == [("reserved",)]
    assert len(_rows(database_url, "SELECT session_id FROM session_plans")) == 1
    assert _rows(database_url, "SELECT ordinal FROM session_plan_objectives") == [(1,)]

    status = client.get(created.headers["location"])
    assert status.status_code == 200
    assert status.json() == created.json()


def test_plan_pins_curriculum_and_rejects_changed_setup(
    client: TestClient, database_url: str
) -> None:
    profile_id, csrf = _sign_in(client)
    changed_preferences = client.patch(
        "/api/v1/me/preferences",
        json={"tutorPace": "gentle"},
        headers={"Origin": "http://web.test", "X-CSRF-Token": csrf, "If-Match": '"1"'},
    )
    assert changed_preferences.status_code == 200
    headers = {
        "Origin": "http://web.test",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": "topic-session-123",
    }
    body = {
        "languageProfileId": profile_id,
        "topic": "my weekend",
        "requestedWords": ["market"],
    }
    created = client.post("/api/v1/sessions", json=body, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["mode"] == "learning"
    assert len(created.json()["planPreview"]["objectives"]) == 1
    assert client.post("/api/v1/sessions", json=body, headers=headers).json() == created.json()
    changed = client.post("/api/v1/sessions", json={**body, "topic": "my work"}, headers=headers)
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "idempotency_conflict"
    assert _rows(
        database_url,
        "SELECT schema_version, curriculum_version, prompt_version, selection_rule_version, mode, "
        "profile_version, preference_version, settings_version, "
        "(setup_digest = (SELECT request_digest FROM sessions LIMIT 1)) "
        "FROM session_plans",
    ) == [(
        "learning_plan_v1", "mori-framework", "mori-framework-v2", "selector-v1",
        "learning", 1, 2, 1, True,
    )]
    assert _rows(database_url, "SELECT kind FROM session_plan_objectives") == [("graded",)]
    assert _rows(database_url, "SELECT requested_words FROM session_plans") == [(["market"],)]


def test_fluent_plan_has_ungraded_focus(client: TestClient, database_url: str) -> None:
    profile_id, csrf = _sign_in(client, "fluent")
    created = client.post(
        "/api/v1/sessions",
        json={"languageProfileId": profile_id, "topic": "food"},
        headers={
            "Origin": "http://web.test",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "fluent-session-123",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["mode"] == "practice"
    assert "food" in created.json()["objective"]
    assert _rows(
        database_url,
        "SELECT mode, selected_level FROM session_plans",
    ) == [("practice", None)]
    assert _rows(
        database_url,
        "SELECT kind, curriculum_item_key FROM session_plan_objectives",
    ) == [("conversation_focus", None)]


@pytest.mark.asyncio
async def test_saved_plan_compiles_and_stale_preferences_block_connection(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    profile_id, csrf = _sign_in(client)
    created = _create(client, profile_id, csrf)
    assert created.status_code == 201
    user_id = _rows(database_url, "SELECT id FROM users")[0][0]
    assert isinstance(user_id, UUID)
    session_id = UUID(created.json()["id"])
    service: SessionService = app.state.session_service

    compiled = await service.load_realtime_config(user_id=user_id, session_id=session_id)
    assert compiled.pair_policy_version == "mori-language-v1"
    assert compiled.base_policy_version == "mori-framework-v2"
    assert compiled.level_policy_version == "beginner"
    assert "# Lesson\n" in compiled.instructions
    assert "Start mostly in the base language" in compiled.instructions
    assert "where they live" in compiled.instructions
    assert '"learningGoal":"Talk with family"' in compiled.instructions

    updated = client.patch(
        "/api/v1/me/preferences",
        json={
            "learningGoal": "Talk at family gatherings",
            "speakingContext": "Casual conversations with relatives",
            "learningNotes": "",
        },
        headers={"Origin": "http://web.test", "X-CSRF-Token": csrf, "If-Match": '"1"'},
    )
    assert updated.status_code == 200
    with pytest.raises(SessionNotConnectable):
        await service.load_realtime_config(user_id=user_id, session_id=session_id)


def test_invalid_setup_does_not_reserve(client: TestClient, database_url: str) -> None:
    profile_id, csrf = _sign_in(client)
    response = client.post(
        "/api/v1/sessions",
        json={"languageProfileId": profile_id, "requestedWords": ["Market", "market"]},
        headers={
            "Origin": "http://web.test",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "invalid-setup-123",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "session_setup_invalid"
    assert _rows(database_url, "SELECT id FROM usage_reservations") == []


def test_planning_failure_rolls_back_reservation(
    client: TestClient, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, csrf = _sign_in(client)

    def no_plan(*_args: object) -> None:
        raise ValueError("no eligible item")

    monkeypatch.setattr(session_application, "build_session_plan", no_plan)
    response = _create(client, profile_id, csrf)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "plan_unavailable"
    assert _rows(database_url, "SELECT id FROM sessions") == []
    assert _rows(database_url, "SELECT id FROM usage_reservations") == []


def test_unsupported_language_blocks_onboarding(client: TestClient, database_url: str) -> None:
    start = client.get("/auth/google/start")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    assert (
        client.get(
            "/auth/google/callback", params={"state": state, "code": "valid-code"}
        ).status_code
        == 302
    )
    me = client.get("/api/v1/me").json()
    pairs = client.get("/api/v1/language-pairs").json()["pairs"]
    assert all(pair["available"] for pair in pairs)
    response = client.post(
        "/api/v1/language-profiles",
        json={
            "baseLanguageId": "english",
            "targetLanguageId": "italian",
            "startingChoice": "beginner",
            "learningGoal": "Talk with family",
            "speakingContext": "Casual conversations with relatives",
        },
        headers={
            "Origin": "http://web.test",
            "X-CSRF-Token": me["csrfToken"],
            "Idempotency-Key": "unsupported-123",
        },
    )
    assert response.status_code == 409
    assert _rows(database_url, "SELECT id FROM usage_reservations") == []


def test_legacy_plan_remains_readable(client: TestClient, database_url: str) -> None:
    profile_id, csrf = _sign_in(client)
    created = _create(client, profile_id, csrf)
    assert created.status_code == 201
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM session_plan_objectives"))
            connection.execute(text("DELETE FROM session_plans"))
            connection.execute(
                text(
                    "INSERT INTO session_plans (session_id, schema_version, curriculum_version, "
                    "selection_rule_version, prompt_version, objective_count, created_at) "
                    "VALUES (:id, 'legacy_placeholder', 'm2-placeholder-v1', "
                    "'m2-placeholder-v1', 'm2-placeholder-v1', 1, CURRENT_TIMESTAMP)"
                ),
                {"id": created.json()["id"]},
            )
            connection.execute(
                text(
                    "INSERT INTO session_plan_objectives (session_id, ordinal, text) "
                    "VALUES (:id, 1, :objective)"
                ),
                {"id": created.json()["id"], "objective": created.json()["objective"]},
            )
    finally:
        engine.dispose()
    status = client.get(created.headers["location"])
    assert status.status_code == 200
    assert status.json()["objective"] == created.json()["objective"]


def test_saved_plan_cannot_be_edited(client: TestClient, database_url: str) -> None:
    profile_id, csrf = _sign_in(client)
    assert _create(client, profile_id, csrf).status_code == 201
    engine = create_engine(database_url)
    try:
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(text("UPDATE session_plans SET topic = 'changed'"))
    finally:
        engine.dispose()


def test_create_requires_auth_csrf_and_idempotency(client: TestClient, database_url: str) -> None:
    no_auth = client.post("/api/v1/sessions", json={"languageProfileId": str(uuid4())})
    assert no_auth.status_code == 401
    profile_id, csrf = _sign_in(client)
    no_origin = client.post(
        "/api/v1/sessions",
        json={"languageProfileId": profile_id},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "new-session-123"},
    )
    assert no_origin.status_code == 403
    no_key = client.post(
        "/api/v1/sessions",
        json={"languageProfileId": profile_id},
        headers={"Origin": "http://web.test", "X-CSRF-Token": csrf},
    )
    assert no_key.status_code == 400
    assert _rows(database_url, "SELECT id FROM sessions") == []


def test_unfinished_onboarding_cannot_reserve_a_session(client: TestClient) -> None:
    start = client.get("/auth/google/start")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    assert (
        client.get(
            "/auth/google/callback", params={"state": state, "code": "valid-code"}
        ).status_code
        == 302
    )
    csrf = client.get("/api/v1/me").json()["csrfToken"]
    response = _create(client, str(uuid4()), csrf)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "onboarding_required"


@pytest.mark.asyncio
async def test_status_checks_ownership_inside_application(client: TestClient, app: FastAPI) -> None:
    profile_id, csrf = _sign_in(client)
    created = _create(client, profile_id, csrf)
    assert created.status_code == 201
    service: SessionService = app.state.session_service

    with pytest.raises(SessionNotFound):
        await service.get(user_id=uuid4(), session_id=UUID(created.json()["id"]))


def test_expired_unconnected_reservation_releases_and_can_be_replaced(
    client: TestClient, database_url: str
) -> None:
    profile_id, csrf = _sign_in(client)
    first = _create(client, profile_id, csrf)
    assert first.status_code == 201
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE usage_reservations SET expires_at = :expired_at"),
                {"expired_at": datetime.now(UTC) - timedelta(seconds=1)},
            )
    finally:
        engine.dispose()

    second = _create(client, profile_id, csrf, key="another-session-123")
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    assert _rows(database_url, "SELECT state FROM sessions ORDER BY created_at") == [
        ("setup_failed",),
        ("planned",),
    ]
    assert sorted(_rows(database_url, "SELECT state FROM usage_reservations")) == [
        ("released",),
        ("reserved",),
    ]
    assert sorted(_rows(database_url, "SELECT kind FROM usage_events")) == [
        ("released",),
        ("reserved",),
        ("reserved",),
    ]
    assert _create(client, profile_id, csrf).json()["state"] == "setup_failed"


@pytest.mark.asyncio
async def test_concurrent_keys_cannot_reserve_the_last_grant(
    app: FastAPI, database_url: str
) -> None:
    # Provision through the existing identity use case without sharing an HTTP client across tasks.
    identity = app.state.identity_service
    started = await identity.start_google_sign_in(return_path="/")
    signed_in = await identity.complete_google_sign_in(state=started.state, code="valid-code")
    await app.state.learner_profile_service.create_profile(
        session_token=signed_in.session_token,
        idempotency_key="profile-setup-123",
        command=CreateProfile(
            base_language_id="english",
            target_language_id="mandarin",
            starting_choice=StartingChoice.BEGINNER,
            correction_preference=CorrectionPreference.BALANCED,
            tutor_pace=TutorPace.LEVEL,
            timezone="UTC",
            interests=(),
            learning_goal="Talk with family",
            speaking_context="Casual conversations with relatives",
        ),
    )
    identity_rows = _rows(
        database_url,
        "SELECT u.id, p.id FROM users u JOIN language_profiles p ON p.user_id = u.id",
    )
    user_id, profile_id = identity_rows[0]
    assert isinstance(user_id, UUID)
    assert isinstance(profile_id, UUID)
    service: SessionService = app.state.session_service

    results = await asyncio.gather(
        service.create(
            user_id=user_id, language_profile_id=profile_id, idempotency_key="concurrent-one-123"
        ),
        service.create(
            user_id=user_id, language_profile_id=profile_id, idempotency_key="concurrent-two-123"
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(result, VoiceEntitlementUnavailable) for result in results) == 1
    assert sum(isinstance(result, tuple) for result in results) == 1
    assert len(_rows(database_url, "SELECT id FROM sessions")) == 1
    assert len(_rows(database_url, "SELECT id FROM usage_reservations")) == 1
