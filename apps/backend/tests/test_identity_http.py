"""Identity HTTP contract tests."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


def _start_login(client: TestClient) -> tuple[str, str]:
    response = client.get("/auth/google/start")
    assert response.status_code == 302
    location = response.headers["location"]
    state = parse_qs(urlsplit(location).query)["state"][0]
    assert response.cookies.get("mori_oauth_state") == state
    return state, location


def _complete_login(client: TestClient, state: str):  # type: ignore[no-untyped-def]
    response = client.get(
        "/auth/google/callback",
        params={"state": state, "code": "valid-code"},
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://web.test/"
    assert response.cookies.get("mori_oauth_state") is None
    return response


def _scalar(database_url: str, sql: str) -> object:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return connection.scalar(text(sql))
    finally:
        engine.dispose()


def _complete_profile(client: TestClient, *, choice: str = "beginner"):
    me = client.get("/api/v1/me").json()
    return client.post(
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


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
    assert response.json()["error"]["requestId"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


def test_google_sign_in_provisions_identity_and_only_stores_token_digest(
    client: TestClient,
    database_url: str,
) -> None:
    state, _ = _start_login(client)
    response = _complete_login(client, state)

    cookie = response.cookies.get("mori_session")
    assert cookie
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]

    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.headers["etag"] == '"1"'
    assert me.json() == {
        "user": {
            "id": me.json()["user"]["id"],
            "email": "learner@example.com",
            "displayName": "Mori Learner",
            "status": "active",
        },
        "version": 1,
        "onboarding": {"complete": False},
        "activeLanguageProfile": None,
        "preferences": None,
        "csrfToken": me.json()["csrfToken"],
    }

    for table in (
        "users",
        "external_identities",
        "grants",
        "auth_sessions",
    ):
        assert _scalar(database_url, f"SELECT count(*) FROM {table}") == 1
    assert _scalar(database_url, "SELECT count(*) FROM language_profiles") == 0
    assert _scalar(database_url, "SELECT count(*) FROM learner_preferences") == 0
    assert _scalar(database_url, "SELECT token_digest FROM auth_sessions") != cookie

    raw_state_count = _scalar(
        database_url,
        f"SELECT count(*) FROM oauth_login_attempts WHERE state_digest = '{state}'",
    )
    assert raw_state_count == 0


def test_callback_replay_does_not_create_another_session(
    client: TestClient,
    database_url: str,
) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)

    replay = client.get(
        "/auth/google/callback",
        params={"state": state, "code": "valid-code"},
    )

    assert replay.status_code == 400
    assert replay.json()["error"]["code"] == "invalid_oauth_flow"
    assert _scalar(database_url, "SELECT count(*) FROM auth_sessions") == 1


def test_callback_requires_state_from_the_browser_that_started_login(
    client: TestClient,
    database_url: str,
) -> None:
    state, _ = _start_login(client)
    client.cookies.delete("mori_oauth_state")

    response = client.get(
        "/auth/google/callback",
        params={"state": state, "code": "valid-code"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_oauth_flow"
    assert _scalar(database_url, "SELECT count(*) FROM auth_sessions") == 0


def test_callback_rejects_a_different_browser_state(
    client: TestClient,
    database_url: str,
) -> None:
    state, _ = _start_login(client)
    client.cookies.set("mori_oauth_state", "different-state")

    response = client.get(
        "/auth/google/callback",
        params={"state": state, "code": "valid-code"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_oauth_flow"
    assert _scalar(database_url, "SELECT count(*) FROM auth_sessions") == 0


def test_separate_sign_ins_reuse_provisioned_records(
    client: TestClient,
    database_url: str,
) -> None:
    first_state, _ = _start_login(client)
    _complete_login(client, first_state)
    second_state, _ = _start_login(client)
    _complete_login(client, second_state)

    assert _scalar(database_url, "SELECT count(*) FROM users") == 1
    assert _scalar(database_url, "SELECT count(*) FROM language_profiles") == 0
    assert _scalar(database_url, "SELECT count(*) FROM learner_preferences") == 0
    assert _scalar(database_url, "SELECT count(*) FROM grants") == 1
    assert _scalar(database_url, "SELECT count(*) FROM auth_sessions") == 2


def test_explicit_onboarding_is_atomic_and_retry_safe(
    client: TestClient, database_url: str
) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)
    catalog = client.get("/api/v1/language-pairs")
    assert catalog.status_code == 200
    assert next(
        pair for pair in catalog.json()["pairs"] if pair["targetLanguageId"] == "mandarin"
    )["available"] is True
    assert next(
        pair for pair in catalog.json()["pairs"] if pair["targetLanguageId"] == "spanish"
    )["available"] is False

    before = client.get("/api/v1/me").json()
    headers = {
        "Origin": "http://web.test",
        "X-CSRF-Token": before["csrfToken"],
        "Idempotency-Key": "profile-setup-123",
    }
    body = {
        "baseLanguageId": "english",
        "targetLanguageId": "mandarin",
        "startingChoice": "unsure",
        "correctionPreference": "light",
        "tutorPace": "gentle",
        "timezone": "Asia/Shanghai",
        "interests": ["Cooking", " cooking ", "Travel"],
        "learningGoal": "Talk with family",
        "speakingContext": "Casual conversations with relatives",
    }
    created = client.post("/api/v1/language-profiles", json=body, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["onboarding"] == {"complete": True}
    assert created.json()["version"] == 2
    assert created.json()["activeLanguageProfile"]["learning"] == {
        "mode": "learning", "startingChoice": "unsure", "provisionalLevel": "beginner",
        "version": 1,
    }
    assert created.json()["preferences"]["interests"] == ["Cooking", "Travel"]
    assert created.json()["preferences"]["learningGoal"] == "Talk with family"
    assert created.json()["preferences"]["speakingContext"] == (
        "Casual conversations with relatives"
    )
    assert _scalar(database_url, "SELECT count(*) FROM language_profiles") == 1
    assert _scalar(database_url, "SELECT count(*) FROM profile_learning_settings") == 1
    assert _scalar(database_url, "SELECT count(*) FROM onboarding_commands") == 1

    replay = client.post("/api/v1/language-profiles", json=body, headers=headers)
    assert replay.status_code == 200
    assert replay.json() == created.json()
    conflict = client.post(
        "/api/v1/language-profiles", json={**body, "startingChoice": "advanced"}, headers=headers
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    duplicate = client.post(
        "/api/v1/language-profiles",
        json={**body, "startingChoice": "advanced"},
        headers={**headers, "Idempotency-Key": "different-setup-456"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "profile_already_confirmed"
    assert client.get("/api/v1/me").json()["activeLanguageProfile"]["learning"] == (
        created.json()["activeLanguageProfile"]["learning"]
    )
    assert _scalar(database_url, "SELECT count(*) FROM language_profiles") == 1


def test_onboarding_rejects_unavailable_pair_and_supports_fluent(client: TestClient) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)
    csrf = client.get("/api/v1/me").json()["csrfToken"]
    headers = {
        "Origin": "http://web.test", "X-CSRF-Token": csrf,
        "Idempotency-Key": "profile-setup-123",
    }
    unavailable = client.post(
        "/api/v1/language-profiles",
        json={
            "baseLanguageId": "english", "targetLanguageId": "spanish",
            "startingChoice": "fluent",
            "learningGoal": "Have natural conversations",
            "speakingContext": "Casual conversations with friends",
        },
        headers=headers,
    )
    assert unavailable.status_code == 409
    assert unavailable.json()["error"]["code"] == "unsupported_language_pair"
    assert client.get("/api/v1/me").json()["activeLanguageProfile"] is None

    fluent = client.post(
        "/api/v1/language-profiles",
        json={
            "baseLanguageId": "english", "targetLanguageId": "mandarin",
            "startingChoice": "fluent",
            "learningGoal": "Have natural conversations",
            "speakingContext": "Casual conversations with friends",
        },
        headers=headers,
    )
    assert fluent.status_code == 201
    assert fluent.json()["activeLanguageProfile"]["learning"] == {
        "mode": "practice", "startingChoice": "fluent", "provisionalLevel": None,
        "version": 1,
    }


def test_onboarding_requires_learning_intent(client: TestClient) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)
    csrf = client.get("/api/v1/me").json()["csrfToken"]
    response = client.post(
        "/api/v1/language-profiles",
        json={"baseLanguageId": "english", "targetLanguageId": "mandarin",
              "startingChoice": "beginner"},
        headers={"Origin": "http://web.test", "X-CSRF-Token": csrf,
                 "Idempotency-Key": "profile-setup-123"},
    )
    assert response.status_code == 422
    assert client.get("/api/v1/me").json()["activeLanguageProfile"] is None


def test_legacy_unconfirmed_profile_is_not_preselected(
    client: TestClient, database_url: str
) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)
    user_id = client.get("/api/v1/me").json()["user"]["id"]
    legacy_id = str(uuid4())
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO language_profiles "
                    "(id, user_id, base_language_id, target_language_id, status) "
                    "VALUES (:id, :user_id, 'english', 'mandarin', 'active')"
                ),
                {"id": legacy_id, "user_id": user_id},
            )
    finally:
        engine.dispose()
    assert client.get("/api/v1/me").json()["activeLanguageProfile"] is None
    confirmed = _complete_profile(client)
    assert confirmed.status_code == 201
    assert confirmed.json()["activeLanguageProfile"]["id"] == legacy_id
    assert _scalar(database_url, "SELECT count(*) FROM language_profiles") == 1


def test_preferences_require_csrf_origin_and_current_etag(client: TestClient) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)
    assert _complete_profile(client).status_code == 201
    me = client.get("/api/v1/me")
    csrf = me.json()["csrfToken"]

    missing_origin = client.patch(
        "/api/v1/me/preferences",
        json={"correctionPreference": "frequent"},
        headers={"If-Match": '"1"', "X-CSRF-Token": csrf},
    )
    assert missing_origin.status_code == 403
    assert missing_origin.json()["error"]["code"] == "csrf_rejected"

    headers = {"Origin": "http://web.test", "X-CSRF-Token": csrf}
    missing_version = client.patch(
        "/api/v1/me/preferences",
        json={"correctionPreference": "frequent"},
        headers=headers,
    )
    assert missing_version.status_code == 428

    updated = client.patch(
        "/api/v1/me/preferences",
        json={
            "correctionPreference": "frequent",
            "tutorPace": "steady",
            "captionsEnabled": True,
            "timezone": "Asia/Shanghai",
        },
        headers={**headers, "If-Match": '"1"'},
    )
    assert updated.status_code == 200
    assert updated.headers["etag"] == '"2"'
    assert updated.json()["preferences"] == {
        "correctionPreference": "frequent",
        "tutorPace": "steady",
        "captionsEnabled": True,
        "timezone": "Asia/Shanghai",
        "interests": [],
        "learningGoal": "Talk with family",
        "speakingContext": "Casual conversations with relatives",
        "learningNotes": "",
        "version": 2,
    }

    changed_goal = client.patch(
        "/api/v1/me/preferences",
        json={
            "learningGoal": "Speak more naturally with family",
            "speakingContext": "Casual chats with relatives",
            "learningNotes": "Practice short follow-up questions",
        },
        headers={**headers, "If-Match": '"2"'},
    )
    assert changed_goal.status_code == 200
    assert changed_goal.json()["preferences"]["learningGoal"] == (
        "Speak more naturally with family"
    )
    assert changed_goal.json()["preferences"]["version"] == 3

    stale = client.patch(
        "/api/v1/me/preferences",
        json={"correctionPreference": "light"},
        headers={**headers, "If-Match": '"1"'},
    )
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "preference_version_conflict"


def test_invalid_preference_payload_is_sanitized(client: TestClient) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)
    me = client.get("/api/v1/me")
    headers = {
        "Origin": "http://web.test",
        "X-CSRF-Token": me.json()["csrfToken"],
        "If-Match": '"1"',
    }

    response = client.patch(
        "/api/v1/me/preferences",
        json={"timezone": "not/a-real-zone"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "not/a-real-zone" not in response.text


def test_logout_revokes_session_and_clears_cookie(client: TestClient) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)
    me = client.get("/api/v1/me")

    response = client.post(
        "/auth/logout",
        headers={
            "Origin": "http://web.test",
            "X-CSRF-Token": me.json()["csrfToken"],
        },
    )

    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert client.get("/api/v1/me").status_code == 401


def test_login_return_path_is_allowlisted(client: TestClient) -> None:
    response = client.get(
        "/auth/google/start",
        params={"return_to": "https://attacker.example/steal"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_return_path"


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ok"}


def test_openapi_contains_the_identity_read_and_mutation(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "get" in paths["/api/v1/me"]
    assert "patch" in paths["/api/v1/me/preferences"]
    assert "post" in paths["/auth/logout"]
