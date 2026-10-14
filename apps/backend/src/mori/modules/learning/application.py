"""Grounded post-session capture, cumulative benchmarking, and recap reads."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mori.modules.curriculum.catalog import CodeCourseCatalog, published_lesson_definition
from mori.modules.learner_profiles.models import LanguageProfileModel, LearnerPreferenceModel
from mori.modules.learning.capture_store import (
    capture_user_insights,
    commit_contribution,
    lock_profile_state,
    store_benchmark,
)
from mori.modules.learning.decisions import DecisionsReviewer
from mori.modules.learning.domain import (
    FinalTurn,
    GroundedUserInsight,
    ValidatedAnalysis,
    validate_candidate,
)
from mori.modules.learning.evidence import (
    AnalysisContext,
    LessonContext,
    QuotedTurn,
    apply_observation_reviews,
)
from mori.modules.learning.extractor import Extractor
from mori.modules.learning.models import (
    AnalysisCorrectionModel,
    AnalysisObservationModel,
    AnalysisObservationTurnModel,
    AnalysisRunModel,
    LanguageItemModel,
    LearnerFileEntryModel,
    LearningContributionModel,
    LessonBenchmarkModel,
    RecapModel,
)
from mori.modules.learning.progress_store import known_language_items, load_learning_history
from mori.modules.sessions.errors import SessionNotFound
from mori.modules.sessions.models import (
    SessionModel,
    SessionPlanModel,
    SessionPlanObjectiveModel,
    SessionTurnModel,
)
from mori.modules.user.persistence import SqlAlchemyUserStore
from mori.persistence.model_registry import load_models


@dataclass(frozen=True, slots=True)
class RecapObservation:
    kind: str
    detail: str
    learner_turn_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class RecapCorrection:
    learner_turn_id: UUID
    before: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class RecapView:
    mode: str
    status: Literal["processing", "ready", "failed"]
    summary: str | None
    observations: tuple[RecapObservation, ...]
    corrections: tuple[RecapCorrection, ...]


class AnalysisService:
    def __init__(
        self,
        *,
        session_maker: async_sessionmaker[AsyncSession],
        extractor: Extractor | None,
        fact_digest_key: str,
        decisions_reviewer: DecisionsReviewer | None = None,
        evidence_probability_threshold: float = 0.8,
    ) -> None:
        load_models()
        self._session_maker = session_maker
        self._extractor = extractor
        self._fact_digest_key = fact_digest_key.encode("utf-8")
        self._decisions_reviewer = decisions_reviewer
        self._evidence_threshold = evidence_probability_threshold

    def _fact_digest(self, profile_id: UUID, category: str, fact: str) -> str:
        canonical = " ".join(fact.casefold().split())
        message = f"{profile_id}:{category}:{canonical}".encode()
        return hmac.new(self._fact_digest_key, message, hashlib.sha256).hexdigest()

    async def process(self, run_id: UUID, *, _refresh_attempt: int = 0) -> None:
        try:
            async with self._session_maker() as db:
                run = await db.get(AnalysisRunModel, run_id)
                if run is None:
                    return
                refreshing = run.status == "ready"
                session = await db.get(SessionModel, run.session_id)
                plan = await db.get(SessionPlanModel, run.session_id)
                profile = (
                    await db.get(LanguageProfileModel, session.language_profile_id)
                    if session is not None
                    else None
                )
                if (
                    session is None
                    or plan is None
                    or profile is None
                    or profile.user_id != session.user_id
                    or session.final_turn_sequence != run.final_turn_sequence
                    or plan.mode != run.mode
                    or plan.curriculum_version != run.curriculum_version
                ):
                    raise ValueError("analysis bundle changed")
                if session.state not in {"analysis_pending", "analysis_failed", "ready"}:
                    return
                await SqlAlchemyUserStore(db).lock_for_session(session.user_id)
                records = (
                    await db.scalars(
                        select(SessionTurnModel)
                        .where(
                            SessionTurnModel.session_id == run.session_id,
                            SessionTurnModel.sequence <= run.final_turn_sequence,
                            SessionTurnModel.text != "",
                        )
                        .order_by(SessionTurnModel.sequence)
                    )
                ).all()
                turns = tuple(FinalTurn(t.id, t.sequence, t.role, t.text) for t in records)
                if len(turns) > 400 or sum(len(turn.text) for turn in turns) > 80_000:
                    raise ValueError("analysis transcript exceeds the supported bound")
                objective = await db.scalar(
                    select(SessionPlanObjectiveModel)
                    .where(SessionPlanObjectiveModel.session_id == run.session_id)
                    .order_by(SessionPlanObjectiveModel.ordinal)
                )
                course = CodeCourseCatalog().course_version(
                    base_language_id=profile.base_language_id,
                    target_language_id=profile.target_language_id,
                    version=run.curriculum_version,
                )
                if course is None:
                    raise ValueError("analysis course is unavailable")
                lesson = None
                if run.mode == "learning":
                    item = next(
                        (
                            item
                            for item in course.items
                            if objective is not None and item.key == objective.curriculum_item_key
                        ),
                        None,
                    )
                    if (
                        item is None
                        or objective is None
                        or objective.kind != "graded"
                        or objective.text != item.label
                        or item.conversation_guidance is None
                    ):
                        raise ValueError("analysis lesson does not match pinned course")
                    lesson = LessonContext(item.key, item.label, item.conversation_guidance)
                definition = (
                    published_lesson_definition(
                        course=course,
                        lesson_key=lesson.key,
                        level=plan.selected_level or "beginner",
                    )
                    if lesson
                    else None
                )
                preferences = await db.get(LearnerPreferenceModel, profile.id)
                context = AnalysisContext(
                    profile.base_language_id,
                    profile.target_language_id,
                    run.curriculum_version,
                    lesson,
                    lesson_definition=definition,
                    known_items=await known_language_items(db, profile.id),
                    language_profile_id=profile.id,
                    session_id=session.id,
                    analysis_run_id=run.id,
                    user_id=session.user_id,
                    occurred_at=session.created_at,
                    learner_timezone=preferences.timezone if preferences else "UTC",
                )
                history = await load_learning_history(db, profile.id, exclude_session_id=session.id)
                if refreshing:
                    contribution = await db.get(LearningContributionModel, session.id)
                    if (
                        contribution is None
                        or contribution.analysis_run_id != run.id
                        or self._decisions_reviewer is None
                        or definition is None
                        or definition.rubric is None
                    ):
                        return
                    current = await db.scalar(
                        select(LessonBenchmarkModel.id)
                        .where(
                            LessonBenchmarkModel.language_profile_id == profile.id,
                            LessonBenchmarkModel.lesson_key == definition.lesson_key,
                            LessonBenchmarkModel.rubric_version == definition.rubric.version,
                            LessonBenchmarkModel.history_revision == history.revision,
                        )
                        .limit(1)
                    )
                    if current is not None:
                        return
                    validated = TypeAdapter(ValidatedAnalysis).validate_python(
                        contribution.accepted_analysis
                    )
            if self._extractor is None and not refreshing:
                raise RuntimeError("analysis provider is not configured")
            review = None
            benchmark = None
            if not refreshing:
                assert self._extractor is not None
                candidate = await self._extractor.extract(
                    mode=run.mode, model=run.extractor_model, context=context, turns=turns
                )
                validated = validate_candidate(
                    candidate, mode=run.mode, turns=turns, context=context
                )
            async with self._session_maker() as db:
                suppressed = (
                    await db.scalars(
                        select(LanguageItemModel).where(
                            LanguageItemModel.language_profile_id == context.language_profile_id,
                            LanguageItemModel.suppressed_at.is_not(None),
                        )
                    )
                ).all()
                forbidden = {(i.form, i.meaning, i.kind) for i in suppressed}
                items = tuple(
                    i
                    for i in validated.language_items
                    if (i.form, i.meaning, i.kind) not in forbidden
                )
                keys = {i.key for i in items}
                suppressed_sources = {
                    p.evidence.learner.turn_id
                    for p in validated.item_practices
                    if p.item_key not in keys
                }
                suppressed_details = set(
                    (
                        await db.scalars(
                            select(AnalysisObservationModel.detail)
                            .join(
                                LearnerFileEntryModel,
                                LearnerFileEntryModel.source_observation_id
                                == AnalysisObservationModel.id,
                            )
                            .where(
                                LearnerFileEntryModel.source_session_id == context.session_id,
                                LearnerFileEntryModel.origin == "learner_edit",
                            )
                        )
                    ).all()
                )
                validated = replace(
                    validated,
                    language_items=items,
                    item_practices=tuple(p for p in validated.item_practices if p.item_key in keys),
                    capability_attempts=tuple(
                        p for p in validated.capability_attempts if set(p.item_keys).issubset(keys)
                    ),
                    observations=tuple(
                        o
                        for o in validated.observations
                        if o.detail not in suppressed_details
                        and not any(e.learner.turn_id in suppressed_sources for e in o.evidence)
                    ),
                )
            if self._decisions_reviewer is not None:
                if not refreshing:
                    review = await self._decisions_reviewer.review_current(
                        context=context, turns=turns, analysis=validated
                    )
                    validated = review.analysis
                if definition is not None and definition.rubric is not None:
                    benchmark = await self._decisions_reviewer.benchmark(
                        context=context, turns=turns, analysis=validated, history=history
                    )
            elif (
                validated.language_items
                or validated.item_practices
                or validated.capability_attempts
                or validated.user_insights
            ):
                raise RuntimeError("structured learning requires Decisions review")
            elif validated.observations:
                assert self._extractor is not None
                reviews = await self._extractor.review_observations(
                    model=run.extractor_model,
                    context=context,
                    turns=turns,
                    observations=validated.observations,
                )
                validated = replace(
                    validated,
                    observations=apply_observation_reviews(validated.observations, reviews),
                )
        except Exception:
            await self._fail(run_id, "extraction_failed")
            raise
        async with self._session_maker() as db, db.begin():
            assert context.user_id is not None and context.language_profile_id is not None
            await SqlAlchemyUserStore(db).lock_for_session(context.user_id)
            state = await lock_profile_state(db, context.language_profile_id)
            locked = await db.scalar(
                select(AnalysisRunModel).where(AnalysisRunModel.id == run_id).with_for_update()
            )
            if locked is None:
                return
            if locked.status == "ready":
                if refreshing and benchmark is not None:
                    contribution = await db.get(LearningContributionModel, locked.session_id)
                    if contribution is not None and contribution.analysis_run_id == run_id:
                        store_benchmark(
                            db,
                            context=context,
                            benchmark=benchmark,
                            applicability_revision=benchmark.history_revision,
                            source_run_id=run_id,
                            evidence_threshold=self._evidence_threshold,
                        )
                        if state.history_revision != benchmark.history_revision:
                            from mori.modules.learning.queue import enqueue_capture

                            await enqueue_capture(db, run_id)
                return
            session = await db.scalar(
                select(SessionModel).where(SessionModel.id == locked.session_id).with_for_update()
            )
            if session is None or session.state not in {
                "analysis_pending",
                "analysis_failed",
                "ready",
            }:
                return
            previous_contribution = await db.get(LearningContributionModel, session.id)
            if previous_contribution is not None:
                previous_run = await db.get(AnalysisRunModel, previous_contribution.analysis_run_id)
                if previous_run is not None and (previous_run.created_at, str(previous_run.id)) > (
                    locked.created_at,
                    str(locked.id),
                ):
                    locked.status = "ready"
                    locked.completed_at = datetime.now(UTC)
                    return
            now = datetime.now(UTC)
            # A new policy replaces only its own unedited projections. Learner edits
            # and learner deletion tombstones remain under the learner's control.
            previous = (
                await db.scalars(
                    select(LearnerFileEntryModel).where(
                        LearnerFileEntryModel.source_session_id == session.id,
                        LearnerFileEntryModel.origin == "capture",
                        LearnerFileEntryModel.deleted_at.is_(None),
                        (LearnerFileEntryModel.kind == "learning")
                        | (
                            (LearnerFileEntryModel.kind == "insight")
                            & (LearnerFileEntryModel.fact_digest.is_(None))
                        ),
                    )
                )
            ).all()
            for entry in previous:
                entry.text = None
                entry.deleted_at = now
                entry.updated_at = now
                entry.version += 1
            db.add(
                RecapModel(
                    id=uuid4(),
                    session_id=session.id,
                    analysis_run_id=run_id,
                    mode=run.mode,
                    summary=validated.summary,
                    created_at=now,
                )
            )
            existing_learning_details = set(
                (
                    await db.scalars(
                        select(AnalysisObservationModel.detail)
                        .join(
                            LearnerFileEntryModel,
                            LearnerFileEntryModel.source_observation_id
                            == AnalysisObservationModel.id,
                        )
                        .where(
                            LearnerFileEntryModel.source_session_id == session.id,
                            LearnerFileEntryModel.kind == "learning",
                            LearnerFileEntryModel.origin == "learner_edit",
                        )
                    )
                ).all()
            )
            for ordinal, observation in enumerate(validated.observations, 1):
                observation_id = uuid4()
                db.add(
                    AnalysisObservationModel(
                        id=observation_id,
                        analysis_run_id=run_id,
                        kind=observation.kind,
                        detail=observation.detail,
                        confidence=observation.confidence,
                        ordinal=ordinal,
                        curriculum_item_key=observation.curriculum_item_key,
                        review_status="supported",
                        review_reason=observation.review_reason
                        or "Supported by Decisions verification.",
                    )
                )
                if observation.detail not in existing_learning_details:
                    db.add(
                        LearnerFileEntryModel(
                            id=uuid4(),
                            language_profile_id=session.language_profile_id,
                            source_observation_id=observation_id,
                            source_session_id=session.id,
                            kind="learning",
                            insight_topic=None,
                            text=observation.detail,
                            origin="capture",
                            confidence=observation.confidence,
                            version=1,
                            created_at=now,
                            updated_at=now,
                            expires_at=None,
                            deleted_at=None,
                        )
                    )
                    existing_learning_details.add(observation.detail)
                for evidence in observation.evidence:
                    opportunity = evidence.opportunity
                    db.add(
                        AnalysisObservationTurnModel(
                            observation_id=observation_id,
                            turn_id=evidence.learner.turn_id,
                            learner_quote=evidence.learner.quote,
                            learner_quote_start=evidence.learner.start,
                            learner_quote_end=evidence.learner.end,
                            opportunity_turn_id=opportunity.turn_id if opportunity else None,
                            opportunity_quote=opportunity.quote if opportunity else None,
                            opportunity_quote_start=opportunity.start if opportunity else None,
                            opportunity_quote_end=opportunity.end if opportunity else None,
                            assistance=evidence.assistance,
                        )
                    )
            for ordinal, correction in enumerate(validated.corrections, 1):
                db.add(
                    AnalysisCorrectionModel(
                        id=uuid4(),
                        analysis_run_id=run_id,
                        learner_turn_id=correction.learner_turn_id,
                        suggestion=correction.suggestion,
                        ordinal=ordinal,
                    )
                )
            validated = await commit_contribution(
                db,
                session=session,
                run=locked,
                context=context,
                analysis=validated,
                state=state,
                review=review,
            )
            if benchmark is not None:
                store_benchmark(
                    db,
                    context=context,
                    benchmark=benchmark,
                    applicability_revision=benchmark.history_revision + 1,
                    source_run_id=run_id,
                    evidence_threshold=self._evidence_threshold,
                )
            # Legacy extraction uses the account-owned suppression controls too.
            legacy_insights = tuple(
                GroundedUserInsight(insight.fact, QuotedTurn(turn.id, turn.text, 0, len(turn.text)))
                for insight in validated.insights
                for turn in turns
                if turn.id == insight.source_turn_id
            )
            legacy_suppressions = (
                await db.execute(
                    select(
                        LearnerFileEntryModel.language_profile_id,
                        LearnerFileEntryModel.insight_topic,
                        LearnerFileEntryModel.fact_digest,
                    )
                    .join(
                        LanguageProfileModel,
                        LanguageProfileModel.id == LearnerFileEntryModel.language_profile_id,
                    )
                    .where(
                        LanguageProfileModel.user_id == session.user_id,
                        LearnerFileEntryModel.kind == "insight",
                        LearnerFileEntryModel.fact_digest.is_not(None),
                    )
                )
            ).all()
            insights = tuple(
                insight
                for insight in validated.user_insights + legacy_insights
                if not any(
                    digest == self._fact_digest(profile_id, topic, insight.text)
                    for profile_id, topic, digest in legacy_suppressions
                    if topic is not None
                )
            )
            await capture_user_insights(
                db, session=session, analysis=replace(validated, user_insights=insights)
            )
            locked.status = "ready"
            locked.failure_code = None
            locked.completed_at = now
            session.state = "ready"
            session.row_version += 1
            session.updated_at = now
            refresh_needed = (
                benchmark is not None and state.history_revision != benchmark.history_revision + 1
            )
        if refresh_needed:
            if _refresh_attempt >= 3:
                raise RuntimeError("learning history kept changing; benchmark requires retry")
            await self.process(run_id, _refresh_attempt=_refresh_attempt + 1)

    async def _fail(self, run_id: UUID, code: str) -> None:
        async with self._session_maker() as db, db.begin():
            run = await db.scalar(
                select(AnalysisRunModel).where(AnalysisRunModel.id == run_id).with_for_update()
            )
            if run is None or run.status == "ready":
                return
            session = await db.scalar(
                select(SessionModel).where(SessionModel.id == run.session_id).with_for_update()
            )
            run.status = "failed"
            run.failure_code = code
            if session is not None and session.state == "analysis_pending":
                session.state = "analysis_failed"
                session.row_version += 1
                session.updated_at = datetime.now(UTC)

    async def recap(self, *, user_id: UUID, session_id: UUID) -> RecapView:
        async with self._session_maker() as db:
            session = await db.scalar(
                select(SessionModel).where(
                    SessionModel.id == session_id, SessionModel.user_id == user_id
                )
            )
            if session is None:
                raise SessionNotFound
            plan = await db.get(SessionPlanModel, session_id)
            mode = plan.mode if plan is not None and plan.mode is not None else "learning"
            if session.state not in {"analysis_pending", "analysis_failed", "ready"}:
                return RecapView(mode, "processing", None, (), ())
            recap = await db.scalar(
                select(RecapModel)
                .where(RecapModel.session_id == session_id)
                .order_by(RecapModel.created_at.desc(), RecapModel.id.desc())
                .limit(1)
            )
            if recap is None:
                return RecapView(
                    mode,
                    "failed" if session.state == "analysis_failed" else "processing",
                    None,
                    (),
                    (),
                )
            run_id = recap.analysis_run_id
            observations = (
                await db.scalars(
                    select(AnalysisObservationModel)
                    .where(AnalysisObservationModel.analysis_run_id == run_id)
                    .order_by(AnalysisObservationModel.ordinal)
                )
            ).all()
            refs = (
                await db.execute(
                    select(
                        AnalysisObservationTurnModel.observation_id,
                        AnalysisObservationTurnModel.turn_id,
                    ).where(
                        AnalysisObservationTurnModel.observation_id.in_(
                            [o.id for o in observations]
                        )
                    )
                )
            ).all()
            by_observation: dict[UUID, list[UUID]] = {}
            for observation_id, turn_id in refs:
                by_observation.setdefault(observation_id, []).append(turn_id)
            corrections = (
                await db.scalars(
                    select(AnalysisCorrectionModel)
                    .where(AnalysisCorrectionModel.analysis_run_id == run_id)
                    .order_by(AnalysisCorrectionModel.ordinal)
                )
            ).all()
            source_ids = [c.learner_turn_id for c in corrections]
            source_turns = (
                await db.scalars(
                    select(SessionTurnModel).where(SessionTurnModel.id.in_(source_ids))
                )
            ).all()
            source_text = {turn.id: turn.text for turn in source_turns}
            return RecapView(
                mode,
                "ready",
                recap.summary,
                tuple(
                    RecapObservation(o.kind, o.detail, tuple(by_observation.get(o.id, ())))
                    for o in observations
                ),
                tuple(
                    RecapCorrection(
                        c.learner_turn_id, source_text.get(c.learner_turn_id, ""), c.suggestion
                    )
                    for c in corrections
                ),
            )
