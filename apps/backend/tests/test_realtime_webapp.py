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


def _planned(client: TestClient) -> tuple[UUID, str]:
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
            "startingChoice": "beginner",
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
    assert client.post(
        f"/api/v1/sessions/{session_id}/connections/{attempt_id}/ack", headers=headers
    ).status_code == 204
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
