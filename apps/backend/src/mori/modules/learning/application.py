"""Post-session capture and recap reads, isolated from progression and memory."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mori.modules.curriculum.catalog import CodeCourseCatalog
from mori.modules.learner_profiles.models import LanguageProfileModel
from mori.modules.learning.domain import FinalTurn, validate_candidate
from mori.modules.learning.evidence import (
    AnalysisContext,
    LessonContext,
    apply_observation_reviews,
)
from mori.modules.learning.extractor import Extractor
from mori.modules.learning.models import (
    AnalysisCorrectionModel,
    AnalysisObservationModel,
    AnalysisObservationTurnModel,
    AnalysisRunModel,
    LearnerFileEntryModel,
    RecapModel,
)
from mori.modules.sessions.errors import SessionNotFound
from mori.modules.sessions.models import (
    SessionModel,
    SessionPlanModel,
    SessionPlanObjectiveModel,
    SessionTurnModel,
)
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
    ) -> None:
        load_models()
        self._session_maker = session_maker
        self._extractor = extractor
        self._fact_digest_key = fact_digest_key.encode("utf-8")

    def _fact_digest(self, profile_id: UUID, category: str, fact: str) -> str:
        canonical = " ".join(fact.casefold().split())
        message = f"{profile_id}:{category}:{canonical}".encode()
        return hmac.new(self._fact_digest_key, message, hashlib.sha256).hexdigest()

    async def process(self, run_id: UUID) -> None:
        try:
            async with self._session_maker() as db:
                run = await db.get(AnalysisRunModel, run_id)
                if run is None or run.status == "ready":
                    return
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
                if session.state not in {"analysis_pending", "analysis_failed"}:
                    return
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
                context = AnalysisContext(
                    profile.base_language_id,
                    profile.target_language_id,
                    run.curriculum_version,
                    lesson,
                )
            if self._extractor is None:
                raise RuntimeError("analysis provider is not configured")
            candidate = await self._extractor.extract(
                mode=run.mode, model=run.extractor_model, context=context, turns=turns
            )
            validated = validate_candidate(candidate, mode=run.mode, turns=turns, context=context)
            if validated.observations:
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
            locked = await db.scalar(
                select(AnalysisRunModel).where(AnalysisRunModel.id == run_id).with_for_update()
            )
            if locked is None or locked.status == "ready":
                return
            session = await db.scalar(
                select(SessionModel).where(SessionModel.id == locked.session_id).with_for_update()
            )
            if session is None or session.state not in {"analysis_pending", "analysis_failed"}:
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
                            LearnerFileEntryModel.deleted_at.is_(None),
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
                        review_reason=observation.review_reason,
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
            suppressed_digests = set(
                (
                    await db.scalars(
                        select(LearnerFileEntryModel.fact_digest).where(
                            LearnerFileEntryModel.language_profile_id
                            == session.language_profile_id,
                            LearnerFileEntryModel.kind == "insight",
                            LearnerFileEntryModel.fact_digest.is_not(None),
                            (LearnerFileEntryModel.deleted_at.is_not(None))
                            | (LearnerFileEntryModel.expires_at > now),
                        )
                    )
                ).all()
            )
            for insight in validated.insights:
                digest = self._fact_digest(session.language_profile_id, insight.topic, insight.fact)
                if digest in suppressed_digests:
                    continue
                db.add(
                    LearnerFileEntryModel(
                        id=uuid4(),
                        language_profile_id=session.language_profile_id,
                        source_observation_id=None,
                        source_session_id=session.id,
                        source_turn_id=insight.source_turn_id,
                        kind="insight",
                        insight_topic=insight.topic,
                        fact_digest=digest,
                        text=insight.fact,
                        origin="capture",
                        confidence=insight.confidence,
                        version=1,
                        created_at=now,
                        updated_at=now,
                        expires_at=now + timedelta(days=90),
                        deleted_at=None,
                    )
                )
                suppressed_digests.add(digest)
            locked.status = "ready"
            locked.failure_code = None
            locked.completed_at = now
            session.state = "ready"
            session.row_version += 1
            session.updated_at = now

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
