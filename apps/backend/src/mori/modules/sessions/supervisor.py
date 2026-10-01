"""Recoverable server owner for live calls and their absolute deadlines."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from time import monotonic
from urllib.parse import quote
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from websockets.asyncio.client import ClientConnection, connect

from mori.modules.access.application import AccessCommands
from mori.modules.access.usage_models import UsageReservationModel
from mori.modules.sessions.application import SessionService
from mori.modules.sessions.models import SessionCallAttemptModel, SessionModel, SessionTurnModel
from mori.modules.sessions.realtime_provider import AmbiguousProviderFailure, OpenAIRealtimeProvider

logger = structlog.get_logger(__name__)
_LEASE = timedelta(seconds=6)


@dataclass(frozen=True, slots=True)
class _Call:
    call_id: str
    state: str
    hard_deadline_at: datetime
    client_ack_deadline_at: datetime
    end_requested_at: datetime | None


class RealtimeSupervisor:
    def __init__(
        self,
        *,
        session_maker: async_sessionmaker[AsyncSession],
        service: SessionService,
        provider: OpenAIRealtimeProvider,
        api_key: str,
    ) -> None:
        self._session_maker = session_maker
        self._service = service
        self._provider = provider
        self._api_key = api_key
        self._owner = uuid4()
        self._runner: asyncio.Task[None] | None = None
        self._watchers: dict[UUID, asyncio.Task[None]] = {}
        self._last_scan = 0.0

    @property
    def healthy(self) -> bool:
        return (
            self._runner is not None
            and not self._runner.done()
            and monotonic() - self._last_scan < 5
        )

    def start(self) -> None:
        if self._runner is not None:
            raise RuntimeError("supervisor already started")
        self._runner = asyncio.create_task(self._run(), name="mori-realtime-supervisor")

    async def stop(self) -> None:
        if self._runner is not None:
            self._runner.cancel()
            await asyncio.gather(self._runner, return_exceptions=True)
        for watcher in self._watchers.values():
            watcher.cancel()
        await asyncio.gather(*self._watchers.values(), return_exceptions=True)
        self._watchers.clear()
        self._runner = None

    async def _run(self) -> None:
        while True:
            try:
                await self._scan()
                self._last_scan = monotonic()
            except asyncio.CancelledError:
                raise
            except Exception:
                await logger.aexception("realtime_supervisor_scan_failed")
            await asyncio.sleep(1)

    async def _scan(self) -> None:
        now = datetime.now(UTC)
        async with self._session_maker() as db, db.begin():
            abandoned = (
                await db.scalars(
                    select(SessionCallAttemptModel)
                    .where(
                        SessionCallAttemptModel.state == "bootstrap_pending",
                        SessionCallAttemptModel.pending_expires_at < now,
                    )
                    .limit(25)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for attempt in abandoned:
                attempt.state = "ambiguous"
                attempt.updated_at = now
                await logger.awarning(
                    "realtime_bootstrap_outcome_unknown", attempt_id=str(attempt.id)
                )
            attempts = (
                await db.scalars(
                    select(SessionCallAttemptModel)
                    .where(
                        SessionCallAttemptModel.provider_call_id.is_not(None),
                        SessionCallAttemptModel.state.in_(("awaiting_client", "active", "ending")),
                        or_(
                            SessionCallAttemptModel.lease_until.is_(None),
                            SessionCallAttemptModel.lease_until < now,
                        ),
                    )
                    .order_by(SessionCallAttemptModel.pending_expires_at)
                    .limit(25)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            ids = []
            for attempt in attempts:
                if attempt.state == "active":
                    attempt.transcript_gap = True
                attempt.sideband_ready_at = None
                attempt.lease_owner = self._owner
                attempt.lease_until = now + _LEASE
                ids.append(attempt.id)
        for attempt_id in ids:
            if attempt_id not in self._watchers or self._watchers[attempt_id].done():
                task = asyncio.create_task(self._watch(attempt_id), name=f"mori-call-{attempt_id}")
                self._watchers[attempt_id] = task
                task.add_done_callback(partial(self._drop_watcher, attempt_id))

    def _drop_watcher(self, attempt_id: UUID, task: asyncio.Task[None]) -> None:
        if self._watchers.get(attempt_id) is task:
            self._watchers.pop(attempt_id, None)

    async def _renew(self, attempt_id: UUID) -> _Call | None:
        now = datetime.now(UTC)
        async with self._session_maker() as db, db.begin():
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            if (
                attempt is None
                or attempt.lease_owner != self._owner
                or attempt.state not in {"awaiting_client", "active", "ending"}
                or attempt.provider_call_id is None
                or attempt.hard_deadline_at is None
                or attempt.client_ack_deadline_at is None
            ):
                return None
            attempt.lease_until = now + _LEASE
            return _Call(
                call_id=attempt.provider_call_id,
                state=attempt.state,
                hard_deadline_at=attempt.hard_deadline_at,
                client_ack_deadline_at=attempt.client_ack_deadline_at,
                end_requested_at=attempt.end_requested_at,
            )

    async def _mark_sideband(self, attempt_id: UUID, *, ready: bool) -> None:
        async with self._session_maker() as db, db.begin():
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            if attempt is not None and attempt.lease_owner == self._owner:
                attempt.sideband_ready_at = datetime.now(UTC) if ready else None
                if not ready and attempt.state == "active":
                    attempt.transcript_gap = True

    async def _watch(self, attempt_id: UUID) -> None:
        socket: ClientConnection | None = None
        loss_started = monotonic()
        try:
            while True:
                call = await self._renew(attempt_id)
                if call is None:
                    return
                now = datetime.now(UTC)
                reason = (
                    "learner_ended"
                    if call.end_requested_at is not None
                    else "time_limit"
                    if now >= call.hard_deadline_at
                    else "connection_failed"
                    if call.state == "awaiting_client" and now >= call.client_ack_deadline_at
                    else "connection_failed"
                    if call.state == "active" and socket is None and monotonic() - loss_started >= 3
                    else None
                )
                if reason is not None:
                    try:
                        await self._provider.hangup(call.call_id)
                    except AmbiguousProviderFailure:
                        await logger.awarning("realtime_hangup_retry", attempt_id=str(attempt_id))
                        await asyncio.sleep(1)
                        continue
                    if socket is not None:
                        drain_until = monotonic() + 1.5
                        while monotonic() < drain_until:
                            try:
                                raw = await asyncio.wait_for(
                                    socket.recv(), timeout=drain_until - monotonic()
                                )
                            except Exception:
                                break
                            if isinstance(raw, str):
                                await self._event(attempt_id, raw)
                        await socket.close()
                        socket = None
                    await self._finish(attempt_id, reason=reason)
                    return
                if socket is None:
                    try:
                        url = (
                            "wss://api.openai.com/v1/realtime?call_id="
                            f"{quote(call.call_id, safe='')}"
                        )
                        socket = await connect(
                            url,
                            additional_headers={"Authorization": f"Bearer {self._api_key}"},
                            open_timeout=1,
                            close_timeout=1,
                        )
                        await self._mark_sideband(attempt_id, ready=True)
                        loss_started = monotonic()
                    except Exception:
                        if socket is not None:
                            await socket.close()
                            socket = None
                        await asyncio.sleep(1)
                        continue
                else:
                    await self._mark_sideband(attempt_id, ready=True)
                try:
                    raw = await asyncio.wait_for(socket.recv(), timeout=1)
                except TimeoutError:
                    continue
                except Exception:
                    await socket.close()
                    socket = None
                    loss_started = monotonic()
                    await self._mark_sideband(attempt_id, ready=False)
                    continue
                if isinstance(raw, str):
                    await self._event(attempt_id, raw)
        finally:
            if socket is not None:
                await socket.close()
            await self._mark_sideband(attempt_id, ready=False)

    async def _event(self, attempt_id: UUID, raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return
        kind = event.get("type")
        if kind in {"conversation.item.added", "response.output_item.added"}:
            item = event.get("item")
            if isinstance(item, dict):
                item_id, item_role = item.get("id"), item.get("role")
                if isinstance(item_id, str) and item_role in {"user", "assistant"}:
                    await self._service.record_item(
                        attempt_id=attempt_id,
                        provider_item_id=item_id,
                        role="learner" if item_role == "user" else "tutor",
                    )
            return
        if kind == "conversation.item.input_audio_transcription.completed":
            role = "learner"
        elif kind == "response.output_audio_transcript.done":
            role = "tutor"
        else:
            return
        item_id, transcript = event.get("item_id"), event.get("transcript")
        if isinstance(item_id, str) and isinstance(transcript, str):
            await self._service.record_turn(
                attempt_id=attempt_id, provider_item_id=item_id, role=role, text=transcript
            )

    async def _finish(self, attempt_id: UUID, *, reason: str) -> None:
        async with self._session_maker() as db, db.begin():
            identified = await db.get(SessionCallAttemptModel, attempt_id)
            if identified is None:
                return
            session = await db.scalar(
                select(SessionModel)
                .where(SessionModel.id == identified.session_id)
                .with_for_update()
            )
            if session is None:
                return
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            if attempt is None or attempt.lease_owner != self._owner or attempt.state == "ended":
                return
            now = datetime.now(UTC)
            reservation = await db.scalar(
                select(UsageReservationModel).where(UsageReservationModel.session_id == session.id)
            )
            if reservation is None:
                raise RuntimeError("live session has no reservation")
            if attempt.connected_at is not None:
                end = min(now, attempt.hard_deadline_at or now)
                session.connected_ms = max(
                    0, int((end - attempt.connected_at).total_seconds() * 1000)
                )
            if reservation.state == "reserved":
                await AccessCommands.release_setup_failure(
                    db, reservation_id=reservation.id, now=now
                )
            if reservation.state == "consumed":
                session.state = "analysis_failed" if attempt.transcript_gap else "analysis_pending"
            else:
                session.state = "setup_failed"
            session.row_version += 1
            session.end_reason = session.end_reason or reason
            session.updated_at = now
            session.final_turn_sequence = await db.scalar(
                select(func.max(SessionTurnModel.sequence)).where(
                    SessionTurnModel.session_id == session.id,
                    SessionTurnModel.text != "",
                )
            )
            attempt.state = "ended"
            attempt.lease_owner = None
            attempt.lease_until = None
            attempt.updated_at = now
