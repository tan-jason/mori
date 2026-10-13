"""Durable wrap-up delivery, timing, and ownership against PostgreSQL."""

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
from sqlalchemy import func, select

from mori.modules.sessions.models import (
    SessionCallAttemptModel,
    SessionControlModel,
    SessionModel,
    SessionTurnModel,
)
from mori.modules.sessions.supervisor import RealtimeSupervisor


class Socket:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[dict[str, object]] = []
        self.fail = fail

    async def send(self, raw: str) -> None:
        self.events.append(json.loads(raw))
        if self.fail:
            raise ConnectionError("ambiguous write")


async def _live(client: TestClient, app: FastAPI) -> tuple[RealtimeSupervisor, UUID]:
    started = client.get("/auth/google/start")
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    assert (
        client.get(
            "/auth/google/callback", params={"state": state, "code": "valid-code"}
        ).status_code
        == 302
    )
    csrf = client.get("/api/v1/me").json()["csrfToken"]
    headers = {
        "Origin": "http://web.test",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": "control-profile",
    }
    profile = client.post(
        "/api/v1/language-profiles",
        headers=headers,
        json={
            "baseLanguageId": "english",
            "targetLanguageId": "mandarin",
            "startingChoice": "beginner",
            "learningGoal": "Talk with family",
            "speakingContext": "Casual conversations",
        },
    )
    assert profile.status_code == 201, profile.text
    headers["Idempotency-Key"] = "control-session"
    created = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "languageProfileId": profile.json()["activeLanguageProfile"]["id"],
        },
    )
    assert created.status_code == 201, created.text
    supervisor = RealtimeSupervisor(
        session_maker=app.state.session_maker,
        service=app.state.session_service,
        provider=SimpleNamespace(),  # type: ignore[arg-type]
        api_key="unused",
    )
    attempt_id = uuid4()
    now = datetime.now(UTC)
    async with app.state.session_maker() as db, db.begin():
        session = await db.get(SessionModel, UUID(created.json()["id"]))
        session.state = "active"
        db.add(
            SessionCallAttemptModel(
                id=attempt_id,
                session_id=session.id,
                attempt_number=1,
                state="active",
                provider_call_id="test-control-call",
                pending_expires_at=now,
                hard_deadline_at=now + timedelta(seconds=89),
                client_ack_deadline_at=now,
                connected_at=now - timedelta(seconds=511),
                lease_owner=supervisor._owner,
                lease_until=now + timedelta(seconds=6),
                created_at=now,
                updated_at=now,
            )
        )
    return supervisor, attempt_id


async def _set_attempt(app: FastAPI, attempt_id: UUID, **fields: object) -> None:
    async with app.state.session_maker() as db, db.begin():
        attempt = await db.get(SessionCallAttemptModel, attempt_id)
        for name, value in fields.items():
            setattr(attempt, name, value)


async def _control(app: FastAPI, attempt_id: UUID) -> SessionControlModel:
    async with app.state.session_maker() as db:
        control = await db.get(SessionControlModel, attempt_id)
        assert control is not None
        return control


@pytest.mark.asyncio
async def test_wrap_up_threshold_ack_and_transcript_exclusion(
    client: TestClient, app: FastAPI
) -> None:
    supervisor, attempt_id = await _live(client, app)
    socket = Socket()
    await _set_attempt(app, attempt_id, hard_deadline_at=datetime.now(UTC) + timedelta(seconds=91))
    await supervisor._wrap_up(attempt_id, socket, reattached=False)  # type: ignore[arg-type]
    assert socket.events == []
    deadline = datetime.now(UTC) + timedelta(seconds=89)
    await _set_attempt(app, attempt_id, hard_deadline_at=deadline)
    await supervisor._wrap_up(attempt_id, socket, reattached=False)  # type: ignore[arg-type]
    assert len(socket.events) == 1
    created = socket.events[0]
    assert created["type"] == "conversation.item.create"
    item = created["item"]
    assert isinstance(item, dict) and item["role"] == "system"
    assert item["content"][0]["type"] == "input_text"
    assert (await _control(app, attempt_id)).state == "uncertain"
    for kind in ("conversation.item.added", "conversation.item.done"):
        await supervisor._event(attempt_id, json.dumps({"type": kind, "item": item}))
    control = await _control(app, attempt_id)
    assert control.state == "acknowledged" and control.acknowledged_at is not None
    await supervisor._event(
        attempt_id,
        json.dumps(
            {
                "type": "response.output_audio_transcript.done",
                "item_id": item["id"],
                "transcript": "Server control context is not tutor speech.",
            }
        ),
    )
    await supervisor._wrap_up(attempt_id, socket, reattached=True)  # type: ignore[arg-type]
    assert len(socket.events) == 1
    async with app.state.session_maker() as db:
        attempt = await db.get(SessionCallAttemptModel, attempt_id)
        assert attempt.hard_deadline_at == deadline
        assert await db.scalar(select(func.count()).select_from(SessionTurnModel)) == 0
    # Normal learner evidence still uses the original transcript path.
    await supervisor._event(
        attempt_id,
        json.dumps(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "learner-message",
                "transcript": "你好",
            }
        ),
    )
    async with app.state.session_maker() as db:
        assert await db.scalar(select(func.count()).select_from(SessionTurnModel)) == 1


@pytest.mark.asyncio
async def test_ambiguous_write_failover_retrieves_before_retry(
    client: TestClient, app: FastAPI
) -> None:
    original, attempt_id = await _live(client, app)
    first = Socket(fail=True)
    with pytest.raises(ConnectionError):
        await original._wrap_up(attempt_id, first, reattached=False)  # type: ignore[arg-type]
    item = first.events[0]["item"]
    replacement = RealtimeSupervisor(
        session_maker=app.state.session_maker,
        service=app.state.session_service,
        provider=SimpleNamespace(),
        api_key="unused",  # type: ignore[arg-type]
    )
    await _set_attempt(app, attempt_id, lease_owner=replacement._owner)
    stale_socket = Socket()
    await original._wrap_up(attempt_id, stale_socket, reattached=True)  # type: ignore[arg-type]
    assert stale_socket.events == [] and await original._renew(attempt_id) is None
    socket = Socket()
    await replacement._wrap_up(attempt_id, socket, reattached=True)  # type: ignore[arg-type]
    assert socket.events[0]["type"] == "conversation.item.retrieve"
    assert socket.events[0]["item_id"] == item["id"]
    await original._event(attempt_id, json.dumps({"type": "conversation.item.added", "item": item}))
    assert (await _control(app, attempt_id)).state == "uncertain"
    await replacement._event(
        attempt_id, json.dumps({"type": "conversation.item.retrieved", "item": item})
    )
    await replacement._wrap_up(attempt_id, socket, reattached=True)  # type: ignore[arg-type]
    assert (await _control(app, attempt_id)).state == "acknowledged"
    assert len(socket.events) == 1


@pytest.mark.asyncio
async def test_confirmed_absence_retries_same_item_and_unknown_errors_do_not(
    client: TestClient, app: FastAPI
) -> None:
    supervisor, attempt_id = await _live(client, app)
    socket = Socket()
    await supervisor._wrap_up(attempt_id, socket, reattached=False)  # type: ignore[arg-type]
    item = socket.events[0]["item"]
    await supervisor._wrap_up(attempt_id, socket, reattached=False)  # type: ignore[arg-type]
    assert len(socket.events) == 1  # No retry before acknowledgment timeout.
    await supervisor._wrap_up(attempt_id, socket, reattached=True)  # type: ignore[arg-type]
    retrieve = socket.events[-1]
    for code, event_id in (
        ("item_not_found", "stale-request"),
        ("server_error", retrieve["event_id"]),
    ):
        await supervisor._event(
            attempt_id,
            json.dumps(
                {
                    "type": "error",
                    "error": {
                        "event_id": event_id,
                        "code": code,
                    },
                }
            ),
        )
        assert (await _control(app, attempt_id)).state == "uncertain"
    await supervisor._event(
        attempt_id,
        json.dumps(
            {
                "type": "error",
                "error": {
                    "event_id": retrieve["event_id"],
                    "code": "item_not_found",
                },
            }
        ),
    )
    assert (await _control(app, attempt_id)).state == "pending"
    async with app.state.session_maker() as db, db.begin():
        control = await db.get(SessionControlModel, attempt_id)
        control.last_attempt_at -= timedelta(seconds=6)
    await supervisor._wrap_up(attempt_id, socket, reattached=False)  # type: ignore[arg-type]
    assert socket.events[-1]["type"] == "conversation.item.create"
    assert socket.events[-1]["item"] == item
    # A duplicate-ID or other create error also requires retrieval, not recreation.
    await supervisor._event(
        attempt_id,
        json.dumps(
            {
                "type": "error",
                "error": {
                    "event_id": socket.events[-1]["event_id"],
                    "code": "invalid_request_error",
                },
            }
        ),
    )
    await supervisor._wrap_up(attempt_id, socket, reattached=True)  # type: ignore[arg-type]
    assert socket.events[-1]["type"] == "conversation.item.retrieve"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"state": "awaiting_client"},
        {"state": "ending"},
        {"end_requested_at": datetime.now(UTC)},
        {"hard_deadline_at": datetime.now(UTC) - timedelta(seconds=1)},
        {"lease_until": datetime.now(UTC) - timedelta(seconds=1)},
    ],
)
async def test_controls_require_live_owned_lease(
    client: TestClient, app: FastAPI, fields: dict[str, object]
) -> None:
    supervisor, attempt_id = await _live(client, app)
    await _set_attempt(app, attempt_id, **fields)
    socket = Socket()
    await supervisor._wrap_up(attempt_id, socket, reattached=True)  # type: ignore[arg-type]
    assert socket.events == []


@pytest.mark.asyncio
async def test_concurrent_delivery_attempts_are_serialized(
    client: TestClient, app: FastAPI
) -> None:
    supervisor, attempt_id = await _live(client, app)
    socket = Socket()
    await asyncio.gather(
        *[
            supervisor._wrap_up(attempt_id, socket, reattached=False)  # type: ignore[arg-type]
            for _ in range(3)
        ]
    )
    assert len(socket.events) == 1


@pytest.mark.asyncio
async def test_retry_budget_is_durable_and_late_ack_can_resolve_it(
    client: TestClient, app: FastAPI
) -> None:
    supervisor, attempt_id = await _live(client, app)
    socket = Socket()
    for _ in range(13):
        await supervisor._wrap_up(attempt_id, socket, reattached=True)  # type: ignore[arg-type]
    control = await _control(app, attempt_id)
    assert control.attempt_count == 12 and control.state == "failed"
    assert control.error_code == "retry_budget_exhausted"
    assert len(socket.events) == 12
    assert sum(event["type"] == "conversation.item.create" for event in socket.events) == 1
    # Exhausting retries does not prove the provider rejected an earlier write.
    await supervisor._event(
        attempt_id,
        json.dumps(
            {
                "type": "conversation.item.done",
                "item": socket.events[0]["item"],
            }
        ),
    )
    assert (await _control(app, attempt_id)).state == "acknowledged"


@pytest.mark.asyncio
async def test_stalled_send_stays_uncertain_and_requires_retrieval(
    client: TestClient, app: FastAPI
) -> None:
    supervisor, attempt_id = await _live(client, app)

    class StalledSocket(Socket):
        async def send(self, raw: str) -> None:
            self.events.append(json.loads(raw))
            await asyncio.Event().wait()

    stalled = StalledSocket()
    with pytest.raises(ConnectionError, match="send timed out"):
        await supervisor._wrap_up(attempt_id, stalled, reattached=False)  # type: ignore[arg-type]
    assert (await _control(app, attempt_id)).state == "uncertain"
    replacement = Socket()
    await supervisor._wrap_up(attempt_id, replacement, reattached=True)  # type: ignore[arg-type]
    assert replacement.events[0]["type"] == "conversation.item.retrieve"
    assert replacement.events[0]["item_id"] == stalled.events[0]["item"]["id"]


@pytest.mark.asyncio
async def test_watch_sends_control_without_forcing_response_and_keeps_deadline(
    client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    supervisor, attempt_id = await _live(client, app)
    async with app.state.session_maker() as db:
        attempt = await db.get(SessionCallAttemptModel, attempt_id)
        deadline = attempt.hard_deadline_at
    hung_up: list[str] = []

    async def hangup(call_id: str) -> None:
        hung_up.append(call_id)

    supervisor._provider = SimpleNamespace(hangup=hangup)

    class WatchSocket(Socket):
        def __init__(self) -> None:
            super().__init__()
            self.reads = 0
            self.closed = False

        async def recv(self) -> str:
            self.reads += 1
            if self.reads == 1:
                await _set_attempt(app, attempt_id, end_requested_at=datetime.now(UTC))
                return json.dumps(
                    {
                        "type": "conversation.item.done",
                        "item": self.events[0]["item"],
                    }
                )
            raise TimeoutError

        async def close(self) -> None:
            self.closed = True

    socket = WatchSocket()

    async def connect(*_args: object, **_kwargs: object) -> WatchSocket:
        return socket

    monkeypatch.setattr("mori.modules.sessions.supervisor.connect", connect)
    await supervisor._watch(attempt_id)
    assert hung_up == ["test-control-call"] and socket.closed
    assert [event["type"] for event in socket.events] == ["conversation.item.create"]
    assert (await _control(app, attempt_id)).state == "acknowledged"
    async with app.state.session_maker() as db:
        attempt = await db.get(SessionCallAttemptModel, attempt_id)
        assert attempt.state == "ended" and attempt.hard_deadline_at == deadline
