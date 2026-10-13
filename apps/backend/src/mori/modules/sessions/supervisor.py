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
from mori.modules.learning.models import AnalysisRunModel
from mori.modules.learning.queue import enqueue_capture
from mori.modules.sessions.application import UNCERTAIN_CALL_WINDOW, SessionService
from mori.modules.sessions.models import (
    SessionCallAttemptModel,
    SessionControlModel,
    SessionModel,
    SessionPlanModel,
    SessionTurnModel,
)
from mori.modules.sessions.realtime_provider import AmbiguousProviderFailure, OpenAIRealtimeProvider

logger = structlog.get_logger(__name__)
_LEASE = timedelta(seconds=6)
_WRAP_UP_WINDOW = timedelta(seconds=90)
_CONTROL_RETRY = timedelta(seconds=5)
_MAX_CONTROL_ATTEMPTS = 12
_WRAP_UP_INSTRUCTIONS = (
    "This session is nearing its time limit. Stop introducing new material. "
    "Finish the current exchange, then briefly recap what was practiced and close warmly. "
    "Let the learner finish speaking and use your next normal turn."
)


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
        extractor_model: str = "",
    ) -> None:
        self._session_maker = session_maker
        self._service = service
        self._provider = provider
        self._api_key = api_key
        self._extractor_model = extractor_model
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
        async with self._session_maker() as db:
            abandoned_ids = (
                await db.scalars(
                    select(SessionCallAttemptModel.id)
                    .where(
                        SessionCallAttemptModel.state == "bootstrap_pending",
                        SessionCallAttemptModel.pending_expires_at < now,
                    )
                    .limit(25)
                )
            ).all()
        for attempt_id in abandoned_ids:
            await self._service.expire_bootstrap_call(attempt_id=attempt_id)
        async with self._session_maker() as db, db.begin():
            expired_unknown = (
                await db.scalars(
                    select(SessionCallAttemptModel)
                    .where(
                        SessionCallAttemptModel.state == "ambiguous",
                        SessionCallAttemptModel.provider_call_id.is_(None),
                        SessionCallAttemptModel.pending_expires_at < now - UNCERTAIN_CALL_WINDOW,
                    )
                    .limit(25)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for attempt in expired_unknown:
                attempt.state = "ended"
                attempt.updated_at = now
                await logger.ainfo("realtime_unknown_call_expired", attempt_id=str(attempt.id))
            cleanup = (
                await db.scalars(
                    select(SessionCallAttemptModel)
                    .where(
                        SessionCallAttemptModel.state == "cleanup_pending",
                        SessionCallAttemptModel.provider_call_id.is_not(None),
                        or_(
                            SessionCallAttemptModel.lease_until.is_(None),
                            SessionCallAttemptModel.lease_until < now,
                        ),
                    )
                    .limit(25)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            cleanup_calls: list[tuple[UUID, str]] = []
            for attempt in cleanup:
                if attempt.provider_call_id is None:
                    continue
                attempt.lease_owner = self._owner
                attempt.lease_until = now + timedelta(seconds=20)
                cleanup_calls.append((attempt.id, attempt.provider_call_id))
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
        for attempt_id, call_id in cleanup_calls:
            if attempt_id not in self._watchers or self._watchers[attempt_id].done():
                task = asyncio.create_task(
                    self._cleanup_call(attempt_id, call_id), name=f"mori-cleanup-{attempt_id}"
                )
                self._watchers[attempt_id] = task
                task.add_done_callback(partial(self._drop_watcher, attempt_id))

    async def _cleanup_call(self, attempt_id: UUID, call_id: str) -> None:
        try:
            await self._provider.hangup(call_id)
        except AmbiguousProviderFailure:
            await logger.awarning("realtime_cleanup_retry", attempt_id=str(attempt_id))
            return
        async with self._session_maker() as db, db.begin():
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            if (
                attempt is None
                or attempt.state != "cleanup_pending"
                or attempt.lease_owner != self._owner
                or attempt.provider_call_id != call_id
            ):
                return
            attempt.state = "ended"
            attempt.lease_owner = None
            attempt.lease_until = None
            attempt.updated_at = datetime.now(UTC)

    def _drop_watcher(self, attempt_id: UUID, task: asyncio.Task[None]) -> None:
        if self._watchers.get(attempt_id) is task:
            self._watchers.pop(attempt_id, None)

    async def _renew(self, attempt_id: UUID) -> _Call | None:
        async with self._session_maker() as db, db.begin():
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            now = datetime.now(UTC)
            if (
                attempt is None
                or attempt.lease_owner != self._owner
                or attempt.lease_until is None
                or attempt.lease_until <= now
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
        attached = False
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
                        attached = True
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
                    await self._wrap_up(attempt_id, socket, reattached=attached)
                    attached = False
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
        if await self._control_event(attempt_id, event):
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

    def _owns_live_call(self, attempt: SessionCallAttemptModel | None, now: datetime) -> bool:
        return bool(
            attempt is not None
            and attempt.lease_owner == self._owner
            and attempt.lease_until is not None
            and attempt.lease_until > now
            and attempt.state == "active"
            and attempt.end_requested_at is None
            and attempt.hard_deadline_at is not None
            and attempt.hard_deadline_at > now
        )

    async def _wrap_up(
        self, attempt_id: UUID, socket: ClientConnection, *, reattached: bool
    ) -> None:
        async with self._session_maker() as db, db.begin():
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            now = datetime.now(UTC)
            if not self._owns_live_call(attempt, now):
                return
            assert attempt is not None and attempt.hard_deadline_at is not None
            if attempt.hard_deadline_at - now > _WRAP_UP_WINDOW:
                return
            control = await db.get(SessionControlModel, attempt_id)
            if control is None:
                control = SessionControlModel(
                    call_attempt_id=attempt_id,
                    provider_item_id=f"item_wrap_{attempt_id.hex}",
                    instructions=_WRAP_UP_INSTRUCTIONS,
                    state="pending",
                    attempt_count=0,
                    created_at=now,
                )
                db.add(control)
            if control.state in {"acknowledged", "failed"}:
                return
            if control.attempt_count >= _MAX_CONTROL_ATTEMPTS:
                control.state = "failed"
                control.error_code = "retry_budget_exhausted"
                await logger.awarning("realtime_wrap_up_unconfirmed", attempt_id=str(attempt_id))
                return
            if (
                not reattached
                and control.last_attempt_at is not None
                and now - control.last_attempt_at < _CONTROL_RETRY
            ):
                return
            # A committed intent can outlive a socket write or process. Resolve it by
            # retrieval before recreating; a successful write is not an acknowledgment.
            request_kind = (
                "retrieve"
                if control.state == "uncertain"
                or (reattached and control.last_attempt_at is not None)
                else "create"
            )
            event_id = f"event_{uuid4().hex}"
            event: dict[str, object] = {
                "type": f"conversation.item.{request_kind}",
                "event_id": event_id,
            }
            if request_kind == "retrieve":
                event["item_id"] = control.provider_item_id
            else:
                event["item"] = {
                    "id": control.provider_item_id,
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "input_text", "text": control.instructions}],
                }
            control.state = "uncertain"
            control.request_kind = request_kind
            control.request_event_id = event_id
            control.last_attempt_at = now
            control.attempt_count += 1
        # Fence the external write with the attempt lock and a bounded send. A new
        # lease owner cannot send concurrently while this transaction holds the lock.
        async with self._session_maker() as db, db.begin():
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            control = await db.get(SessionControlModel, attempt_id)
            if (
                not self._owns_live_call(attempt, datetime.now(UTC))
                or control is None
                or control.state != "uncertain"
                or control.request_event_id != event_id
            ):
                return
            try:
                await asyncio.wait_for(socket.send(json.dumps(event)), timeout=1)
            except TimeoutError as exc:
                # The watch loop treats a receive timeout as idle. A timed-out
                # send needs a fresh socket and retrieval of the committed intent.
                raise ConnectionError("wrap-up send timed out") from exc

    async def _control_event(self, attempt_id: UUID, event: dict[str, object]) -> bool:
        kind = event.get("type")
        if kind not in {
            "conversation.item.added",
            "conversation.item.done",
            "conversation.item.retrieved",
            "response.output_item.added",
            "conversation.item.input_audio_transcription.completed",
            "response.output_audio_transcript.done",
            "error",
        }:
            return False
        async with self._session_maker() as db, db.begin():
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            control = await db.get(SessionControlModel, attempt_id)
            if control is None:
                return False
            item = event.get("item")
            matching_item = (
                isinstance(item, dict) and item.get("id") == control.provider_item_id
            ) or event.get("item_id") == control.provider_item_id
            now = datetime.now(UTC)
            # Drain acknowledgments while ending, but never let an expired owner
            # modify the new owner's delivery state.
            if (
                attempt is None
                or attempt.lease_owner != self._owner
                or attempt.lease_until is None
                or attempt.lease_until <= now
            ):
                return matching_item
            if control.state == "acknowledged":
                return matching_item
            if (
                kind
                in {
                    "conversation.item.added",
                    "conversation.item.done",
                    "conversation.item.retrieved",
                }
                and isinstance(item, dict)
                and matching_item
            ):
                if (
                    item.get("type") == "message"
                    and item.get("role") == "system"
                    and item.get("content")
                    == [{"type": "input_text", "text": control.instructions}]
                ):
                    control.state = "acknowledged"
                    control.acknowledged_at = now
                    control.error_code = None
                else:
                    control.state = "failed"
                    control.error_code = "control_item_mismatch"
                return True
            error = event.get("error")
            if not isinstance(error, dict) or error.get("event_id") != control.request_event_id:
                return matching_item
            code = error.get("code")
            control.error_code = code[:160] if isinstance(code, str) else "unknown_error"
            if control.request_kind == "retrieve" and code in {
                "item_not_found",
                "conversation_item_not_found",
            }:
                control.state = "pending"
            # Unrecognized errors never establish absence. Keep retrieving instead
            # of claiming exactly-once delivery or blindly recreating the message.
            return True

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
            if session.state == "analysis_pending":
                if session.final_turn_sequence is None:
                    session.state = "analysis_failed"
                else:
                    await self._queue_analysis(db, session, now)
            attempt.state = "ended"
            attempt.lease_owner = None
            attempt.lease_until = None
            attempt.updated_at = now

    async def _queue_analysis(self, db: AsyncSession, session: SessionModel, now: datetime) -> None:
        assert session.final_turn_sequence is not None
        has_learner_turn = await db.scalar(
            select(SessionTurnModel.id)
            .where(
                SessionTurnModel.session_id == session.id,
                SessionTurnModel.sequence <= session.final_turn_sequence,
                SessionTurnModel.role == "learner",
                SessionTurnModel.text != "",
            )
            .limit(1)
        )
        if has_learner_turn is None or not self._extractor_model:
            session.state = "analysis_failed"
            return
        plan = await db.get(SessionPlanModel, session.id)
        if plan is None or plan.mode not in {"learning", "practice"}:
            session.state = "analysis_failed"
            return
        run_id = uuid4()
        db.add(
            AnalysisRunModel(
                id=run_id,
                session_id=session.id,
                extractor_model=self._extractor_model,
                curriculum_version=plan.curriculum_version,
                mode=plan.mode,
                final_turn_sequence=session.final_turn_sequence,
                status="pending",
                created_at=now,
            )
        )
        await enqueue_capture(db, run_id)
