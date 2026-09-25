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

from mori.modules.sessions.application import SessionService
from mori.modules.sessions.errors import SessionNotFound, VoiceEntitlementUnavailable


def _sign_in(client: TestClient) -> tuple[str, str]:
    start = client.get("/auth/google/start")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    assert client.get(
        "/auth/google/callback", params={"state": state, "code": "valid-code"}
    ).status_code == 302
    me = client.get("/api/v1/me").json()
    return me["activeLanguageProfile"]["id"], me["csrfToken"]


def _create(
    client: TestClient, profile_id: str, csrf: str, key: str = "new-session-123"
):  # type: ignore[no-untyped-def]
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
    assert created.json()["connectedLimitMs"] == 1_200_000
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


def test_create_requires_auth_csrf_and_idempotency(client: TestClient, database_url: str) -> None:
    no_auth = client.post(
        "/api/v1/sessions", json={"languageProfileId": str(uuid4())}
    )
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


@pytest.mark.asyncio
async def test_status_checks_ownership_inside_application(
    client: TestClient, app: FastAPI
) -> None:
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
    await identity.complete_google_sign_in(state=started.state, code="valid-code")
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
