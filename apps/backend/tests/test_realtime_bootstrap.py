"""Durable bootstrap intent and provider SDP contract."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from mori.modules.sessions.application import SessionService
from mori.modules.sessions.errors import SessionNotConnectable
from mori.modules.sessions.realtime_provider import (
    AmbiguousProviderFailure,
    DefinitiveProviderFailure,
    OpenAIRealtimeProvider,
)


def _planned_session(client: TestClient, database_url: str) -> tuple[UUID, UUID]:
    start = client.get("/auth/google/start")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    callback = client.get("/auth/google/callback", params={"state": state, "code": "valid-code"})
    assert callback.status_code == 302
    me = client.get("/api/v1/me").json()
    headers = {
        "Origin": "http://web.test",
        "X-CSRF-Token": me["csrfToken"],
        "Idempotency-Key": "profile-bootstrap-123",
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
        headers={**headers, "Idempotency-Key": "session-bootstrap-123"},
    )
    assert session.status_code == 201
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            user_id = connection.scalar(text("SELECT id FROM users"))
    finally:
        engine.dispose()
    assert isinstance(user_id, UUID)
    return user_id, UUID(session.json()["id"])


def _rows(database_url: str, sql: str) -> list[tuple[object, ...]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(sql)).all()]
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_prepare_call_commits_manifest_before_provider_and_blocks_duplicate(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    user_id, session_id = _planned_session(client, database_url)
    service: SessionService = app.state.session_service
    prepared = await service.prepare_call(
        user_id=user_id,
        session_id=session_id,
        model_alias="realtime-test",
        voice_alias="test-voice",
    )
    assert "You are Mori" in prepared.instructions
    assert _rows(database_url, "SELECT state FROM sessions") == [("connecting",)]
    assert _rows(database_url, "SELECT state, provider_call_id FROM session_call_attempts") == [
        ("bootstrap_pending", None)
    ]
    assert _rows(
        database_url,
        "SELECT model_alias, voice_alias, length(instructions_sha256) FROM session_prompt_builds",
    ) == [("realtime-test", "test-voice", 64)]
    with pytest.raises(SessionNotConnectable):
        await service.prepare_call(
            user_id=user_id,
            session_id=session_id,
            model_alias="realtime-test",
            voice_alias="test-voice",
        )
    await service.record_provider_call(
        attempt_id=prepared.attempt_id, provider_call_id="rtc_example"
    )
    assert _rows(database_url, "SELECT state, provider_call_id FROM session_call_attempts") == [
        ("awaiting_client", "rtc_example")
    ]


@pytest.mark.asyncio
async def test_known_provider_failure_releases_grant_but_ambiguous_failure_blocks_retry(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    user_id, session_id = _planned_session(client, database_url)
    service: SessionService = app.state.session_service
    prepared = await service.prepare_call(
        user_id=user_id,
        session_id=session_id,
        model_alias="realtime-test",
        voice_alias="test-voice",
    )
    await service.record_provider_failure(attempt_id=prepared.attempt_id, ambiguous=True)
    assert _rows(database_url, "SELECT state FROM session_call_attempts") == [("ambiguous",)]
    assert _rows(database_url, "SELECT state FROM usage_reservations") == [("reserved",)]
    assert _rows(database_url, "SELECT state FROM sessions") == [("connecting",)]


@pytest.mark.asyncio
async def test_definitive_provider_failure_releases_reservation(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    user_id, session_id = _planned_session(client, database_url)
    service: SessionService = app.state.session_service
    prepared = await service.prepare_call(
        user_id=user_id,
        session_id=session_id,
        model_alias="realtime-test",
        voice_alias="test-voice",
    )
    await service.record_provider_failure(attempt_id=prepared.attempt_id, ambiguous=False)
    assert _rows(database_url, "SELECT state FROM sessions") == [("setup_failed",)]
    assert _rows(database_url, "SELECT state FROM usage_reservations") == [("released",)]
    assert _rows(database_url, "SELECT kind FROM usage_events ORDER BY created_at") == [
        ("reserved",),
        ("released",),
    ]


@pytest.mark.asyncio
async def test_concurrent_prepare_creates_one_attempt(
    client: TestClient, app: FastAPI, database_url: str
) -> None:
    user_id, session_id = _planned_session(client, database_url)
    service: SessionService = app.state.session_service
    results = await asyncio.gather(
        *(
            service.prepare_call(
                user_id=user_id,
                session_id=session_id,
                model_alias="realtime-test",
                voice_alias="test-voice",
            )
            for _ in range(2)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(result, SessionNotConnectable) for result in results) == 1
    assert len(_rows(database_url, "SELECT id FROM session_call_attempts")) == 1


@pytest.mark.asyncio
async def test_provider_sends_server_configuration_and_reads_call_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(
            201, headers={"Location": "/v1/realtime/calls/rtc_example"}, text="v=0\r\nanswer"
        )

    original_client = httpx2.AsyncClient
    monkeypatch.setattr(
        httpx2,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx2.MockTransport(handler), **kwargs),
    )
    provider = OpenAIRealtimeProvider(api_key="server-secret")
    result = await provider.create_call(
        offer_sdp="v=0\r\noffer",
        instructions="Tutor instructions",
        model="realtime-test",
        voice="test-voice",
        safety_identifier="hashed-learner",
    )
    assert result.call_id == "rtc_example"
    assert result.answer_sdp == "v=0\r\nanswer"
    request = captured[0]
    assert request.url.path == "/v1/realtime/calls"
    assert request.headers["OpenAI-Safety-Identifier"] == "hashed-learner"
    body = request.content.decode()
    assert '"instructions":"Tutor instructions"' in body
    assert '"voice":"test-voice"' in body
    assert "v=0\r\noffer" in body
    assert "server-secret" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "location", "error_type"),
    [
        (400, "", DefinitiveProviderFailure),
        (502, "", AmbiguousProviderFailure),
        (201, "", AmbiguousProviderFailure),
    ],
)
async def test_provider_failure_classification(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    location: str,
    error_type: type[Exception],
) -> None:
    original_client = httpx2.AsyncClient
    monkeypatch.setattr(
        httpx2,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx2.MockTransport(
                lambda _request: httpx2.Response(status, headers={"Location": location}, text="v=0")
            ),
            **kwargs,
        ),
    )
    provider = OpenAIRealtimeProvider(api_key="server-secret")
    with pytest.raises(error_type):
        await provider.create_call(
            offer_sdp="v=0",
            instructions="Tutor",
            model="model",
            voice="voice",
            safety_identifier="hashed-learner",
        )
