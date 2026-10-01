"""Idempotent, transactional first-session planning."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mori.modules.access.application import AccessCommands, IntroGrant
from mori.modules.access.usage_models import UsageReservationModel
from mori.modules.curriculum.catalog import CodeCourseCatalog
from mori.modules.curriculum.domain import (
    SELECTION_RULE_VERSION,
    PlannedObjective,
    PlanningContext,
    PublishedCourse,
    build_session_plan,
)
from mori.modules.learner_profiles.domain import PlanningProfile
from mori.modules.learner_profiles.errors import OnboardingRequired, UnsupportedLanguagePair
from mori.modules.learner_profiles.models import LearnerPreferenceModel
from mori.modules.learner_profiles.persistence import SqlAlchemyLearnerProfileStore
from mori.modules.sessions.domain import normalize_requested_words, normalize_topic
from mori.modules.sessions.errors import (
    IdempotencyConflict,
    InvalidIdempotencyKey,
    InvalidSessionSetup,
    PlanUnavailable,
    SessionNotConnectable,
    SessionNotFound,
    VoiceEntitlementUnavailable,
    VoiceRetryLimitReached,
)
from mori.modules.sessions.models import (
    SessionCallAttemptModel,
    SessionModel,
    SessionPlanModel,
    SessionPlanObjectiveModel,
    SessionPromptBuildModel,
    SessionTurnModel,
)
from mori.modules.sessions.prompt import (
    BASE_POLICY_VERSION,
    CompiledRealtimeConfig,
    PromptObjective,
    PromptPlan,
    PromptProfile,
    compile_realtime_config,
)
from mori.modules.user.domain import UserStatus
from mori.modules.user.persistence import SqlAlchemyUserStore

_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_-]{7,127}\Z")
_RESERVATION_TTL = timedelta(minutes=10)
_BOOTSTRAP_PENDING_TTL = timedelta(seconds=30)
UNCERTAIN_CALL_WINDOW = timedelta(hours=2)
_MAX_UNCERTAIN_CALLS = 3


@dataclass(frozen=True, slots=True)
class SessionView:
    id: UUID
    state: str
    row_version: int
    connected_limit_ms: int
    connected_ms: int
    reservation_expires_at: datetime
    objective: str
    objectives: tuple[str, ...]
    mode: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class _SessionSetup:
    profile_id: UUID
    topic: str | None
    requested_words: tuple[str, ...]
    key_digest: str
    request_digest: str

    @classmethod
    def from_request(
        cls,
        *,
        profile_id: UUID,
        idempotency_key: str,
        topic: str | None,
        requested_words: tuple[str, ...],
    ) -> _SessionSetup:
        if not _KEY_PATTERN.fullmatch(idempotency_key):
            raise InvalidIdempotencyKey
        try:
            topic = normalize_topic(topic)
            requested_words = normalize_requested_words(requested_words)
        except ValueError as error:
            raise InvalidSessionSetup from error
        request_digest = sha256(
            json.dumps(
                {
                    "languageProfileId": str(profile_id),
                    "topic": topic,
                    "requestedWords": requested_words,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        return cls(
            profile_id=profile_id,
            topic=topic,
            requested_words=requested_words,
            key_digest=sha256(idempotency_key.encode("ascii")).hexdigest(),
            request_digest=request_digest,
        )


@dataclass(frozen=True, slots=True)
class _SelectedPlan:
    profile: PlanningProfile
    course: PublishedCourse
    objectives: tuple[PlannedObjective, ...]


@dataclass(frozen=True, slots=True)
class PreparedCall:
    attempt_id: UUID
    session_id: UUID
    instructions: str
    model_alias: str
    voice_alias: str


class SessionService:
    def __init__(
        self,
        *,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_maker = session_maker

    async def create(
        self,
        *,
        user_id: UUID,
        language_profile_id: UUID,
        idempotency_key: str,
        topic: str | None = None,
        requested_words: tuple[str, ...] = (),
    ) -> tuple[SessionView, bool]:
        setup = _SessionSetup.from_request(
            profile_id=language_profile_id,
            idempotency_key=idempotency_key,
            topic=topic,
            requested_words=requested_words,
        )
        async with self._session_maker() as db, db.begin():
            # The account lock serializes duplicate keys and competing attempts
            # to reserve the same final grant, including across API processes.
            account = await SqlAlchemyUserStore(db).lock_for_session(user_id)
            if account is None or account.status != UserStatus.ACTIVE:
                raise VoiceEntitlementUnavailable
            if account.onboarding_completed_at is None:
                raise OnboardingRequired
            replay = await self._replay(db, user_id=user_id, setup=setup)
            if replay is not None:
                return replay, False
            selected = await self._select_plan(db, user_id=user_id, setup=setup)
            now = datetime.now(UTC)
            await self._check_uncertain_call_limit(db, user_id=user_id, now=now)
            grant = await self._claim_grant(db, user_id=user_id, now=now)
            return await self._save_plan(
                db, user_id=user_id, setup=setup, selected=selected, grant=grant, now=now
            ), True

    async def _replay(
        self, db: AsyncSession, *, user_id: UUID, setup: _SessionSetup
    ) -> SessionView | None:
        existing = await db.scalar(
            select(SessionModel).where(
                SessionModel.user_id == user_id,
                SessionModel.creation_key_digest == setup.key_digest,
            )
        )
        if existing is None:
            return None
        if (
            existing.language_profile_id != setup.profile_id
            or (
                existing.request_digest is not None
                and existing.request_digest != setup.request_digest
            )
            or (
                existing.request_digest is None
                and (setup.topic is not None or setup.requested_words)
            )
        ):
            raise IdempotencyConflict
        return await self._view(db, existing)

    @staticmethod
    async def _select_plan(
        db: AsyncSession, *, user_id: UUID, setup: _SessionSetup
    ) -> _SelectedPlan:
        profile = await SqlAlchemyLearnerProfileStore(db).for_planning(
            user_id=user_id, profile_id=setup.profile_id
        )
        if profile is None:
            raise OnboardingRequired
        course = await CodeCourseCatalog().published_course(
            base_language_id=profile.base_language_id,
            target_language_id=profile.target_language_id,
        )
        if course is None:
            raise UnsupportedLanguagePair
        try:
            objectives = build_session_plan(
                PlanningContext(
                    mode=profile.mode.value,
                    provisional_level=(
                        profile.provisional_level.value if profile.provisional_level else None
                    ),
                    topic=setup.topic,
                    requested_words=setup.requested_words,
                ),
                course,
            )
        except ValueError as error:
            raise PlanUnavailable from error
        return _SelectedPlan(profile=profile, course=course, objectives=objectives)

    async def _claim_grant(self, db: AsyncSession, *, user_id: UUID, now: datetime) -> IntroGrant:
        grant = await AccessCommands.claim_intro_grant(db, user_id=user_id, now=now)
        if grant is None:
            raise VoiceEntitlementUnavailable
        held = grant.held
        if held is not None:
            previous = await db.get(SessionModel, held.session_id)
            if held.expires_at > now or previous is None or previous.state != "planned":
                raise VoiceEntitlementUnavailable
            await self._transition(
                db,
                previous.id,
                expected="planned",
                version=previous.row_version,
                target="setup_failed",
                now=now,
            )
            await AccessCommands.release_expired(db, reservation_id=held.id, now=now)
        return grant

    @staticmethod
    async def _check_uncertain_call_limit(
        db: AsyncSession, *, user_id: UUID, now: datetime
    ) -> None:
        # The provider limits Realtime sessions to 60 minutes. The two-hour
        # window leaves room for a late create result and provider expiry.
        count = await db.scalar(
            select(func.count(SessionCallAttemptModel.id))
            .join(SessionModel, SessionModel.id == SessionCallAttemptModel.session_id)
            .where(
                SessionModel.user_id == user_id,
                or_(
                    SessionCallAttemptModel.state == "cleanup_pending",
                    and_(
                        SessionCallAttemptModel.state == "ambiguous",
                        SessionCallAttemptModel.pending_expires_at > now - UNCERTAIN_CALL_WINDOW,
                    ),
                ),
            )
        )
        if (count or 0) >= _MAX_UNCERTAIN_CALLS:
            raise VoiceRetryLimitReached

    async def _save_plan(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        setup: _SessionSetup,
        selected: _SelectedPlan,
        grant: IntroGrant,
        now: datetime,
    ) -> SessionView:
        profile, course, objectives = selected.profile, selected.course, selected.objectives
        mode = profile.mode.value
        level = profile.provisional_level.value if profile.provisional_level is not None else None
        if mode == "learning" and level is None:
            raise PlanUnavailable
        session = SessionModel(
            user_id=user_id,
            language_profile_id=setup.profile_id,
            creation_key_digest=setup.key_digest,
            request_digest=setup.request_digest,
            state="created",
            row_version=1,
            connected_limit_ms=grant.connected_limit_ms,
            connected_ms=0,
            created_at=now,
            updated_at=now,
        )
        db.add(session)
        await db.flush()
        reservation_expires_at = await AccessCommands.reserve_intro(
            db, grant_id=grant.id, session_id=session.id, now=now, ttl=_RESERVATION_TTL
        )
        await self._transition(
            db, session.id, expected="created", version=1, target="reserved", now=now
        )
        db.add(
            SessionPlanModel(
                session_id=session.id,
                curriculum_version=course.curriculum_version,
                selection_rule_version=SELECTION_RULE_VERSION,
                prompt_version=BASE_POLICY_VERSION,
                schema_version="learning_plan_v1",
                mode=mode,
                profile_version=profile.profile_version,
                preference_version=profile.preference_version,
                settings_version=profile.settings_version,
                selected_level=level,
                topic=setup.topic,
                requested_words=list(setup.requested_words),
                setup_digest=setup.request_digest,
                base_policy_version=BASE_POLICY_VERSION,
                pair_policy_version=course.pair_policy_version,
                level_policy_version=("practice-v1" if mode == "practice" else f"{level}-v1"),
                objective_count=len(objectives),
                created_at=now,
            )
        )
        for ordinal, objective in enumerate(objectives, start=1):
            db.add(
                SessionPlanObjectiveModel(
                    session_id=session.id,
                    ordinal=ordinal,
                    text=objective.label,
                    kind=objective.kind,
                    curriculum_item_key=objective.curriculum_item_key,
                )
            )
        await self._transition(
            db, session.id, expected="reserved", version=2, target="planned", now=now
        )
        return SessionView(
            id=session.id,
            state="planned",
            row_version=3,
            connected_limit_ms=grant.connected_limit_ms,
            connected_ms=0,
            reservation_expires_at=reservation_expires_at,
            objective=objectives[0].label,
            objectives=tuple(item.label for item in objectives),
            mode=mode,
            created_at=now,
        )

    async def get(self, *, user_id: UUID, session_id: UUID) -> SessionView:
        async with self._session_maker() as db:
            session = await db.scalar(
                select(SessionModel).where(
                    SessionModel.id == session_id, SessionModel.user_id == user_id
                )
            )
            if session is None:
                raise SessionNotFound
            return await self._view(db, session)

    async def load_realtime_config(
        self, *, user_id: UUID, session_id: UUID
    ) -> CompiledRealtimeConfig:
        """Compile the saved plan after checking its current connection eligibility.

        The later provider bootstrap must repeat these checks in its own short
        transaction before it creates a call attempt. No provider request belongs
        in this read transaction.
        """
        async with self._session_maker() as db:
            session = await db.scalar(
                select(SessionModel).where(
                    SessionModel.id == session_id, SessionModel.user_id == user_id
                )
            )
            if session is None:
                raise SessionNotFound
            reservation = await db.scalar(
                select(UsageReservationModel).where(UsageReservationModel.session_id == session_id)
            )
            if (
                session.state != "planned"
                or reservation is None
                or reservation.state != "reserved"
                or reservation.expires_at <= datetime.now(UTC)
            ):
                raise SessionNotConnectable
            plan = await db.get(SessionPlanModel, session_id)
            if (
                plan is None
                or plan.schema_version != "learning_plan_v1"
                or plan.prompt_version != plan.base_policy_version
                or plan.setup_digest != session.request_digest
            ):
                raise SessionNotConnectable
            profile = await SqlAlchemyLearnerProfileStore(db).for_planning(
                user_id=user_id, profile_id=session.language_profile_id
            )
            if profile is None or (
                plan.profile_version,
                plan.preference_version,
                plan.settings_version,
            ) != (
                profile.profile_version,
                profile.preference_version,
                profile.settings_version,
            ):
                raise SessionNotConnectable
            if plan.mode != profile.mode.value or (
                plan.snapshot_id is None
                and plan.selected_level
                != (profile.provisional_level.value if profile.provisional_level else None)
            ):
                raise SessionNotConnectable
            preferences = await db.get(LearnerPreferenceModel, profile.id)
            course = CodeCourseCatalog().course_version(
                base_language_id=profile.base_language_id,
                target_language_id=profile.target_language_id,
                version=plan.curriculum_version,
            )
            if preferences is None or course is None or plan.requested_words is None:
                raise SessionNotConnectable
            objectives = (
                await db.scalars(
                    select(SessionPlanObjectiveModel)
                    .where(SessionPlanObjectiveModel.session_id == session_id)
                    .order_by(SessionPlanObjectiveModel.ordinal)
                )
            ).all()
            if len(objectives) != plan.objective_count or any(
                objective.kind is None for objective in objectives
            ):
                raise SessionNotConnectable
            prompt_plan = PromptPlan(
                schema_version=plan.schema_version,
                mode=plan.mode or "",
                selected_level=plan.selected_level,
                curriculum_version=plan.curriculum_version,
                base_policy_version=plan.base_policy_version or "",
                pair_policy_version=plan.pair_policy_version or "",
                level_policy_version=plan.level_policy_version or "",
                topic=plan.topic,
                requested_words=tuple(plan.requested_words),
                objectives=tuple(
                    PromptObjective(
                        kind=objective.kind or "",
                        label=objective.text,
                        curriculum_item_key=objective.curriculum_item_key,
                    )
                    for objective in objectives
                ),
            )
            prompt_profile = PromptProfile(
                base_language_id=profile.base_language_id,
                target_language_id=profile.target_language_id,
                correction_preference=preferences.correction_preference,
                tutor_pace=preferences.tutor_pace,
            )
            try:
                return compile_realtime_config(
                    plan=prompt_plan, profile=prompt_profile, course=course
                )
            except ValueError as error:
                raise SessionNotConnectable from error

    async def prepare_call(
        self, *, user_id: UUID, session_id: UUID, model_alias: str, voice_alias: str
    ) -> PreparedCall:
        """Commit the call intent and prompt build before any provider request."""
        if not model_alias or not voice_alias or len(model_alias) > 128 or len(voice_alias) > 128:
            raise ValueError("model and voice aliases are required")
        compiled = await self.load_realtime_config(user_id=user_id, session_id=session_id)
        async with self._session_maker() as db, db.begin():
            account = await SqlAlchemyUserStore(db).lock_for_session(user_id)
            if account is None or account.status != UserStatus.ACTIVE:
                raise VoiceEntitlementUnavailable
            session = await db.scalar(
                select(SessionModel)
                .where(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .with_for_update()
            )
            if session is None:
                raise SessionNotFound
            reservation = await db.scalar(
                select(UsageReservationModel)
                .where(UsageReservationModel.session_id == session_id)
                .with_for_update()
            )
            now = datetime.now(UTC)
            await self._check_uncertain_call_limit(db, user_id=user_id, now=now)
            if (
                session.state != "planned"
                or reservation is None
                or reservation.state != "reserved"
                or reservation.expires_at <= now
            ):
                raise SessionNotConnectable
            plan = await db.get(SessionPlanModel, session_id)
            profile = await SqlAlchemyLearnerProfileStore(db).for_planning(
                user_id=user_id, profile_id=session.language_profile_id
            )
            if (
                plan is None
                or profile is None
                or (
                    plan.profile_version,
                    plan.preference_version,
                    plan.settings_version,
                )
                != (
                    profile.profile_version,
                    profile.preference_version,
                    profile.settings_version,
                )
            ):
                raise SessionNotConnectable
            last_number = await db.scalar(
                select(func.max(SessionCallAttemptModel.attempt_number)).where(
                    SessionCallAttemptModel.session_id == session_id
                )
            )
            attempt = SessionCallAttemptModel(
                session_id=session_id,
                attempt_number=(last_number or 0) + 1,
                state="bootstrap_pending",
                pending_expires_at=now + _BOOTSTRAP_PENDING_TTL,
                created_at=now,
                updated_at=now,
            )
            db.add(attempt)
            await db.flush()
            db.add(
                SessionPromptBuildModel(
                    call_attempt_id=attempt.id,
                    session_id=session_id,
                    base_policy_version=compiled.base_policy_version,
                    pair_policy_version=compiled.pair_policy_version,
                    level_policy_version=compiled.level_policy_version,
                    voice_policy_version=compiled.voice_policy_version,
                    model_alias=model_alias,
                    voice_alias=voice_alias,
                    instructions_sha256=compiled.instructions_sha256,
                    created_at=now,
                )
            )
            await self._transition(
                db,
                session_id,
                expected="planned",
                version=session.row_version,
                target="connecting",
                now=now,
            )
            return PreparedCall(
                attempt_id=attempt.id,
                session_id=session_id,
                instructions=compiled.instructions,
                model_alias=model_alias,
                voice_alias=voice_alias,
            )

    async def record_provider_call(
        self, *, attempt_id: UUID, provider_call_id: str, live_cap_seconds: int = 120
    ) -> datetime | None:
        """Persist provider identity before an SDP answer may be returned."""
        if not provider_call_id or len(provider_call_id) > 160:
            raise ValueError("invalid provider call ID")
        if live_cap_seconds <= 0:
            raise ValueError("live call cap must be positive")
        async with self._session_maker() as db, db.begin():
            session_id = await db.scalar(
                select(SessionCallAttemptModel.session_id).where(
                    SessionCallAttemptModel.id == attempt_id
                )
            )
            if session_id is None:
                raise SessionNotConnectable
            session = await db.scalar(
                select(SessionModel).where(SessionModel.id == session_id).with_for_update()
            )
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            if session is None or attempt is None:
                raise SessionNotConnectable
            now = datetime.now(UTC)
            if attempt.state in {"bootstrap_pending", "ambiguous"} and session.state in {
                "ending",
                "setup_failed",
            }:
                attempt.provider_call_id = provider_call_id
                attempt.state = "cleanup_pending"
                attempt.updated_at = now
                if session.state == "ending":
                    await self._release_failed_setup(db, session=session, now=now, ambiguous=True)
                return None
            if attempt.state != "bootstrap_pending" or session.state != "connecting":
                raise SessionNotConnectable
            attempt.provider_call_id = provider_call_id
            attempt.state = "awaiting_client"
            attempt.client_ack_deadline_at = now + timedelta(seconds=30)
            attempt.hard_deadline_at = now + timedelta(
                milliseconds=min(session.connected_limit_ms, live_cap_seconds * 1000)
            )
            attempt.updated_at = now
            return attempt.hard_deadline_at

    async def wait_for_sideband(self, *, user_id: UUID, session_id: UUID, attempt_id: UUID) -> None:
        until = asyncio.get_running_loop().time() + 5
        while True:
            async with self._session_maker() as db:
                attempt = await db.scalar(
                    select(SessionCallAttemptModel)
                    .join(SessionModel, SessionModel.id == SessionCallAttemptModel.session_id)
                    .where(
                        SessionCallAttemptModel.id == attempt_id,
                        SessionCallAttemptModel.session_id == session_id,
                        SessionModel.user_id == user_id,
                    )
                )
                if attempt is None or attempt.state not in {"awaiting_client", "active"}:
                    raise SessionNotConnectable
                if (
                    attempt.sideband_ready_at is not None
                    and attempt.sideband_ready_at > datetime.now(UTC) - timedelta(seconds=3)
                ):
                    return
            if asyncio.get_running_loop().time() >= until:
                raise SessionNotConnectable
            await asyncio.sleep(0.1)

    async def acknowledge_call(self, *, user_id: UUID, session_id: UUID, attempt_id: UUID) -> None:
        async with self._session_maker() as db, db.begin():
            session = await db.scalar(
                select(SessionModel)
                .where(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .with_for_update()
            )
            if session is None:
                raise SessionNotFound
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(
                    SessionCallAttemptModel.id == attempt_id,
                    SessionCallAttemptModel.session_id == session_id,
                )
                .with_for_update()
            )
            now = datetime.now(UTC)
            if attempt is not None and attempt.state == "active" and session.state == "active":
                return
            if (
                attempt is None
                or attempt.state != "awaiting_client"
                or (
                    attempt.client_ack_deadline_at is None
                    or attempt.client_ack_deadline_at <= now
                    or attempt.hard_deadline_at is None
                    or attempt.hard_deadline_at <= now
                    or attempt.sideband_ready_at is None
                    or attempt.sideband_ready_at <= now - timedelta(seconds=3)
                )
            ):
                raise SessionNotConnectable
            if session.state != "connecting":
                raise SessionNotConnectable
            await self._transition(
                db,
                session_id,
                expected="connecting",
                version=session.row_version,
                target="active",
                now=now,
            )
            attempt.state = "active"
            attempt.connected_at = now
            attempt.updated_at = now
            session.session_expires_at = attempt.hard_deadline_at

    async def request_end(self, *, user_id: UUID, session_id: UUID) -> None:
        async with self._session_maker() as db, db.begin():
            session = await db.scalar(
                select(SessionModel)
                .where(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .with_for_update()
            )
            if session is None:
                raise SessionNotFound
            if session.state in {"setup_failed", "analysis_pending", "ready", "analysis_failed"}:
                return
            if session.state not in {"connecting", "active", "ending"}:
                raise SessionNotConnectable
            now = datetime.now(UTC)
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(
                    SessionCallAttemptModel.session_id == session_id,
                    SessionCallAttemptModel.state.in_(
                        ("bootstrap_pending", "awaiting_client", "active", "ending")
                    ),
                )
                .with_for_update()
            )
            if attempt is None:
                raise SessionNotConnectable
            attempt.end_requested_at = attempt.end_requested_at or now
            if attempt.provider_call_id is not None:
                attempt.state = "ending"
            attempt.updated_at = now
            if session.state != "ending":
                await self._transition(
                    db,
                    session_id,
                    expected=session.state,
                    version=session.row_version,
                    target="ending",
                    now=now,
                )
            session.end_reason = session.end_reason or "learner_ended"

    async def record_turn(
        self, *, attempt_id: UUID, provider_item_id: str, role: str, text: str
    ) -> None:
        if role not in {"learner", "tutor"} or not provider_item_id or not text.strip():
            return
        if len(provider_item_id) > 160 or len(text) > 16000:
            return
        async with self._session_maker() as db, db.begin():
            attempt = await db.get(SessionCallAttemptModel, attempt_id)
            if attempt is None or attempt.state not in {"active", "ending"}:
                return
            session = await db.scalar(
                select(SessionModel).where(SessionModel.id == attempt.session_id).with_for_update()
            )
            if session is None or session.state not in {"active", "ending"}:
                return
            existing = await db.scalar(
                select(SessionTurnModel).where(
                    SessionTurnModel.session_id == session.id,
                    SessionTurnModel.provider_item_id == provider_item_id,
                    SessionTurnModel.role == role,
                )
            )
            if existing is not None and existing.text:
                return
            if existing is not None:
                existing.text = text.strip()
            else:
                number = await db.scalar(
                    select(func.max(SessionTurnModel.sequence)).where(
                        SessionTurnModel.session_id == session.id
                    )
                )
                db.add(
                    SessionTurnModel(
                        session_id=session.id,
                        provider_item_id=provider_item_id,
                        role=role,
                        sequence=(number or 0) + 1,
                        text=text.strip(),
                        created_at=datetime.now(UTC),
                    )
                )
            now = datetime.now(UTC)
            if role == "learner":
                reservation = await db.scalar(
                    select(UsageReservationModel).where(
                        UsageReservationModel.session_id == session.id
                    )
                )
                if reservation is not None and reservation.state == "reserved":
                    await AccessCommands.consume_intro(db, reservation_id=reservation.id, now=now)

    async def record_item(self, *, attempt_id: UUID, provider_item_id: str, role: str) -> None:
        if role not in {"learner", "tutor"} or not provider_item_id or len(provider_item_id) > 160:
            return
        async with self._session_maker() as db, db.begin():
            attempt = await db.get(SessionCallAttemptModel, attempt_id)
            if attempt is None or attempt.state not in {"active", "ending"}:
                return
            session = await db.scalar(
                select(SessionModel).where(SessionModel.id == attempt.session_id).with_for_update()
            )
            if session is None or session.state not in {"active", "ending"}:
                return
            existing = await db.scalar(
                select(SessionTurnModel.id).where(
                    SessionTurnModel.session_id == session.id,
                    SessionTurnModel.provider_item_id == provider_item_id,
                    SessionTurnModel.role == role,
                )
            )
            if existing is not None:
                return
            number = await db.scalar(
                select(func.max(SessionTurnModel.sequence)).where(
                    SessionTurnModel.session_id == session.id
                )
            )
            db.add(
                SessionTurnModel(
                    session_id=session.id,
                    provider_item_id=provider_item_id,
                    role=role,
                    sequence=(number or 0) + 1,
                    text="",
                    created_at=datetime.now(UTC),
                )
            )

    async def record_provider_failure(
        self, *, attempt_id: UUID, ambiguous: bool, provider_call_id: str | None = None
    ) -> None:
        """Fail unusable setup while retaining any uncertain provider call for cleanup."""
        await self._fail_bootstrap_attempt(
            attempt_id=attempt_id, ambiguous=ambiguous, provider_call_id=provider_call_id
        )

    async def expire_bootstrap_call(self, *, attempt_id: UUID) -> None:
        await self._fail_bootstrap_attempt(attempt_id=attempt_id, ambiguous=True, expired=True)

    async def _fail_bootstrap_attempt(
        self,
        *,
        attempt_id: UUID,
        ambiguous: bool,
        provider_call_id: str | None = None,
        expired: bool = False,
    ) -> None:
        if provider_call_id is not None and (
            not ambiguous or not provider_call_id or len(provider_call_id) > 160
        ):
            raise ValueError("invalid uncertain provider call ID")
        async with self._session_maker() as db, db.begin():
            session_id = await db.scalar(
                select(SessionCallAttemptModel.session_id).where(
                    SessionCallAttemptModel.id == attempt_id
                )
            )
            if session_id is None:
                raise SessionNotConnectable
            session = await db.scalar(
                select(SessionModel).where(SessionModel.id == session_id).with_for_update()
            )
            attempt = await db.scalar(
                select(SessionCallAttemptModel)
                .where(SessionCallAttemptModel.id == attempt_id)
                .with_for_update()
            )
            if session is None or attempt is None:
                raise SessionNotConnectable
            if attempt.state in {"ambiguous", "cleanup_pending", "provider_failed"}:
                if provider_call_id is not None and attempt.state == "ambiguous":
                    attempt.provider_call_id = provider_call_id
                    attempt.state = "cleanup_pending"
                    attempt.updated_at = datetime.now(UTC)
                elif not ambiguous and attempt.state == "ambiguous":
                    attempt.state = "provider_failed"
                    attempt.updated_at = datetime.now(UTC)
                    session.end_reason = "connection_failed"
                return
            if expired and attempt.state != "bootstrap_pending":
                return
            if attempt.state != "bootstrap_pending":
                raise SessionNotConnectable
            now = datetime.now(UTC)
            if expired and attempt.pending_expires_at >= now:
                return
            attempt.provider_call_id = provider_call_id
            if provider_call_id is not None:
                attempt.state = "cleanup_pending"
            else:
                attempt.state = "ambiguous" if ambiguous else "provider_failed"
            attempt.updated_at = now
            await self._release_failed_setup(db, session=session, now=now, ambiguous=ambiguous)

    async def _release_failed_setup(
        self, db: AsyncSession, *, session: SessionModel, now: datetime, ambiguous: bool
    ) -> None:
        if session.state not in {"connecting", "ending"}:
            raise SessionNotConnectable
        await self._transition(
            db,
            session.id,
            expected=session.state,
            version=session.row_version,
            target="setup_failed",
            now=now,
        )
        session.end_reason = session.end_reason or (
            "provider_outcome_unknown" if ambiguous else "connection_failed"
        )
        reservation = await db.scalar(
            select(UsageReservationModel).where(UsageReservationModel.session_id == session.id)
        )
        if reservation is None:
            raise RuntimeError("call attempt has no reservation")
        await AccessCommands.release_setup_failure(db, reservation_id=reservation.id, now=now)

    async def _view(self, db: AsyncSession, session: SessionModel) -> SessionView:
        plan = await db.get(SessionPlanModel, session.id)
        objectives = (
            await db.scalars(
                select(SessionPlanObjectiveModel)
                .where(SessionPlanObjectiveModel.session_id == session.id)
                .order_by(SessionPlanObjectiveModel.ordinal)
            )
        ).all()
        reservation = await db.scalar(
            select(UsageReservationModel).where(UsageReservationModel.session_id == session.id)
        )
        if plan is None or not objectives or reservation is None:
            raise RuntimeError("planned session is missing its plan, objective, or reservation")
        return SessionView(
            id=session.id,
            state=session.state,
            row_version=session.row_version,
            connected_limit_ms=session.connected_limit_ms,
            connected_ms=session.connected_ms,
            reservation_expires_at=reservation.expires_at,
            objective=objectives[0].text,
            objectives=tuple(item.text for item in objectives),
            mode=plan.mode or "learning",
            created_at=session.created_at,
        )

    @staticmethod
    async def _transition(
        db: AsyncSession,
        session_id: UUID,
        *,
        expected: str,
        version: int,
        target: str,
        now: datetime,
    ) -> None:
        result = await db.execute(
            update(SessionModel)
            .where(
                SessionModel.id == session_id,
                SessionModel.state == expected,
                SessionModel.row_version == version,
            )
            .values(state=target, row_version=version + 1, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise RuntimeError("session transition lost its expected state")
