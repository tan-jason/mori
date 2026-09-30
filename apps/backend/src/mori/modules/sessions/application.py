"""Idempotent, transactional first-session planning."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, update
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
)
from mori.modules.sessions.models import SessionModel, SessionPlanModel, SessionPlanObjectiveModel
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
                select(UsageReservationModel).where(
                    UsageReservationModel.session_id == session_id
                )
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
