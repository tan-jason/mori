"""Identity HTTP contract tests."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

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
        "onboarding": {"complete": False},
        "activeLanguageProfile": {
            "id": me.json()["activeLanguageProfile"]["id"],
            "baseLanguageId": "english",
            "targetLanguageId": "mandarin",
            "status": "active",
        },
        "preferences": {
            "correctionPreference": "balanced",
            "tutorPace": "level",
            "captionsEnabled": False,
            "timezone": "America/New_York",
            "version": 1,
        },
        "csrfToken": me.json()["csrfToken"],
    }

    for table in (
        "users",
        "external_identities",
        "language_profiles",
        "learner_preferences",
        "grants",
        "auth_sessions",
    ):
        assert _scalar(database_url, f"SELECT count(*) FROM {table}") == 1
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
    assert _scalar(database_url, "SELECT count(*) FROM language_profiles") == 1
    assert _scalar(database_url, "SELECT count(*) FROM learner_preferences") == 1
    assert _scalar(database_url, "SELECT count(*) FROM grants") == 1
    assert _scalar(database_url, "SELECT count(*) FROM auth_sessions") == 2


def test_preferences_require_csrf_origin_and_current_etag(client: TestClient) -> None:
    state, _ = _start_login(client)
    _complete_login(client, state)
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
        "version": 2,
    }

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
