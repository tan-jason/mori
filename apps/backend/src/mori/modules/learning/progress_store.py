"""Complete accepted learning history and bounded, owned planning projections."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import cast
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from mori.modules.curriculum.progress import (
    CriterionDistribution,
    LessonBenchmark,
    PracticeOccurrence,
    ProfileProgress,
    RecallItem,
)
from mori.modules.learning.decisions import (
    BenchmarkScore,
    HistoricalLearningRecord,
    LearningHistory,
)
from mori.modules.learning.decisions import (
    LessonBenchmark as DecisionsBenchmark,
)
from mori.modules.learning.domain import ValidatedAnalysis
from mori.modules.learning.evidence import (
    AcceptedObservation,
    Assistance,
    KnownLanguageItem,
    LanguageItemKind,
    PracticeEvidence,
    QuotedTurn,
)
from mori.modules.learning.models import (
    AnalysisObservationModel,
    AnalysisObservationTurnModel,
    AnalysisRunModel,
    LanguageItemModel,
    LearnerFileEntryModel,
    LearningContributionModel,
    LearningOccurrenceModel,
    LessonBenchmarkModel,
    ProfileLearningStateModel,
    RecapModel,
)
from mori.modules.sessions.models import SessionModel


def json_record(value: object) -> dict[str, object]:
    encoded = json.loads(json.dumps(asdict(value), default=str))  # type: ignore[call-overload]
    if not isinstance(encoded, dict):
        raise ValueError("record must be an object")
    return cast(dict[str, object], encoded)


async def eligible_item_ids(
    db: AsyncSession, profile_id: UUID, item_ids: tuple[UUID, ...] | list[UUID]
) -> frozenset[UUID]:
    if not item_ids:
        return frozenset()
    active_source = exists(
        select(LearningOccurrenceModel.id)
        .join(
            LearningContributionModel,
            LearningContributionModel.analysis_run_id == LearningOccurrenceModel.analysis_run_id,
        )
        .where(
            LearningOccurrenceModel.item_id == LanguageItemModel.id,
            LearningOccurrenceModel.language_profile_id == profile_id,
            LearningOccurrenceModel.suppressed_at.is_(None),
        )
    )
    return frozenset(
        (
            await db.scalars(
                select(LanguageItemModel.id).where(
                    LanguageItemModel.id.in_(item_ids),
                    LanguageItemModel.language_profile_id == profile_id,
                    LanguageItemModel.suppressed_at.is_(None),
                    active_source,
                )
            )
        ).all()
    )


async def known_language_items(db: AsyncSession, profile_id: UUID) -> tuple[KnownLanguageItem, ...]:
    rows = (
        await db.scalars(
            select(LanguageItemModel)
            .where(
                LanguageItemModel.language_profile_id == profile_id,
            )
            .order_by(LanguageItemModel.introduced_at, LanguageItemModel.id)
        )
    ).all()
    eligible = await eligible_item_ids(db, profile_id, [row.id for row in rows])
    return tuple(
        KnownLanguageItem(
            row.id,
            row.form,
            row.meaning,
            cast(LanguageItemKind, row.kind),
            tuple(row.capability_keys),
        )
        for row in rows
        if row.id in eligible
    )


async def load_learning_history(
    db: AsyncSession, profile_id: UUID, *, exclude_session_id: UUID | None = None
) -> LearningHistory:
    state = await db.get(ProfileLearningStateModel, profile_id)
    query = select(LearningContributionModel).where(
        LearningContributionModel.language_profile_id == profile_id
    )
    if exclude_session_id is not None:
        query = query.where(LearningContributionModel.session_id != exclude_session_id)
    contributions = (
        await db.scalars(
            query.order_by(
                LearningContributionModel.occurred_at,
                LearningContributionModel.session_id,
            )
        )
    ).all()
    items = (
        await db.scalars(
            select(LanguageItemModel).where(LanguageItemModel.language_profile_id == profile_id)
        )
    ).all()
    eligible = await eligible_item_ids(db, profile_id, [item.id for item in items])
    active_observations = set(
        (
            await db.execute(
                select(AnalysisObservationModel.analysis_run_id, AnalysisObservationModel.detail)
                .join(
                    LearnerFileEntryModel,
                    LearnerFileEntryModel.source_observation_id == AnalysisObservationModel.id,
                )
                .where(
                    LearnerFileEntryModel.language_profile_id == profile_id,
                    LearnerFileEntryModel.deleted_at.is_(None),
                    LearnerFileEntryModel.origin == "capture",
                )
            )
        ).all()
    )
    records: list[HistoricalLearningRecord] = []
    for contribution in contributions:
        accepted = TypeAdapter(ValidatedAnalysis).validate_python(contribution.accepted_analysis)
        allowed = {item.key for item in accepted.language_items if item.known_item_id in eligible}
        suppressed_sources = {
            p.evidence.learner.turn_id for p in accepted.item_practices if p.item_key not in allowed
        }
        records.append(
            HistoricalLearningRecord(
                profile_id,
                contribution.session_id,
                contribution.analysis_run_id,
                contribution.occurred_at,
                contribution.lesson_key,
                contribution.content_version,
                tuple(item for item in accepted.language_items if item.key in allowed),
                tuple(p for p in accepted.item_practices if p.item_key in allowed),
                tuple(
                    p
                    for p in accepted.capability_attempts
                    if all(key in allowed for key in p.item_keys)
                ),
                tuple(
                    o
                    for o in accepted.observations
                    if (contribution.analysis_run_id, o.detail) in active_observations
                    and not any(e.learner.turn_id in suppressed_sources for e in o.evidence)
                ),
            )
        )
    # Original, reviewed legacy evidence remains eligible. Editable summaries and
    # quote-free older records do not become invented structured proficiency.
    latest_recap = (
        select(RecapModel.analysis_run_id)
        .where(RecapModel.session_id == SessionModel.id)
        .order_by(RecapModel.created_at.desc(), RecapModel.id.desc())
        .limit(1)
        .correlate(SessionModel)
        .scalar_subquery()
    )
    legacy_query = (
        select(AnalysisObservationModel, AnalysisRunModel, SessionModel)
        .join(AnalysisRunModel, AnalysisRunModel.id == AnalysisObservationModel.analysis_run_id)
        .join(SessionModel, SessionModel.id == AnalysisRunModel.session_id)
        .join(
            LearnerFileEntryModel,
            LearnerFileEntryModel.source_observation_id == AnalysisObservationModel.id,
        )
        .where(
            SessionModel.language_profile_id == profile_id,
            AnalysisRunModel.id == latest_recap,
            AnalysisObservationModel.review_status == "supported",
            LearnerFileEntryModel.origin == "capture",
            LearnerFileEntryModel.deleted_at.is_(None),
            ~exists(
                select(LearningContributionModel.session_id).where(
                    LearningContributionModel.session_id == SessionModel.id
                )
            ),
        )
        .order_by(SessionModel.created_at, AnalysisObservationModel.ordinal)
    )
    if exclude_session_id is not None:
        legacy_query = legacy_query.where(SessionModel.id != exclude_session_id)
    legacy_rows = (await db.execute(legacy_query)).all()
    refs = (
        (
            await db.scalars(
                select(AnalysisObservationTurnModel).where(
                    AnalysisObservationTurnModel.observation_id.in_(
                        [o.id for o, _, _ in legacy_rows]
                    )
                )
            )
        ).all()
        if legacy_rows
        else []
    )
    refs_by_observation: dict[UUID, list[AnalysisObservationTurnModel]] = {}
    for ref in refs:
        refs_by_observation.setdefault(ref.observation_id, []).append(ref)
    grouped: dict[UUID, list[AcceptedObservation]] = {}
    for observation, run, _session in legacy_rows:
        evidence = []
        for ref in refs_by_observation.get(observation.id, []):
            if ref.learner_quote is None:
                continue
            assert ref.learner_quote_start is not None and ref.learner_quote_end is not None
            opportunity = None
            if ref.opportunity_turn_id is not None:
                assert ref.opportunity_quote is not None
                assert (
                    ref.opportunity_quote_start is not None
                    and ref.opportunity_quote_end is not None
                )
                opportunity = QuotedTurn(
                    ref.opportunity_turn_id,
                    ref.opportunity_quote,
                    ref.opportunity_quote_start,
                    ref.opportunity_quote_end,
                )
            evidence.append(
                PracticeEvidence(
                    QuotedTurn(
                        ref.turn_id,
                        ref.learner_quote,
                        ref.learner_quote_start,
                        ref.learner_quote_end,
                    ),
                    opportunity,
                    cast(Assistance, ref.assistance),
                )
            )
        if evidence and observation.curriculum_item_key is not None:
            grouped.setdefault(run.id, []).append(
                AcceptedObservation(
                    observation.kind,
                    observation.detail,
                    observation.confidence,
                    observation.curriculum_item_key,
                    tuple(evidence),
                    observation.review_reason,
                )
            )
    seen = set()
    for _, run, session in legacy_rows:
        if run.id in seen or run.id not in grouped:
            continue
        seen.add(run.id)
        records.append(
            HistoricalLearningRecord(
                profile_id,
                session.id,
                run.id,
                session.created_at,
                grouped[run.id][0].curriculum_item_key,
                run.curriculum_version,
                observations=tuple(grouped[run.id]),
            )
        )
    records.sort(key=lambda r: (r.occurred_at, str(r.session_id), str(r.analysis_run_id)))
    return LearningHistory(profile_id, state.history_revision if state else 0, tuple(records), True)


def _distribution(score: BenchmarkScore, threshold: float, levels: int) -> CriterionDistribution:
    probabilities = tuple(
        next((p.probability for p in score.result.probabilities if p.value == index), 0.0)
        for index in range(levels)
    )
    if score.result.type != "score" or not probabilities or abs(sum(probabilities) - 1) > 0.001:
        # Refused/unobserved scores remain unusable, with no invented accomplishment.
        probabilities = (1.0,) + (0.0,) * (levels - 1)
        assessable = False
    else:
        assessable = (
            score.assessable.type == "predicate"
            and (score.assessable.probability or 0) >= threshold
        )
    return CriterionDistribution(score.key, assessable, probabilities)


async def load_profile_progress(db: AsyncSession, profile_id: UUID) -> ProfileProgress:
    state = await db.get(ProfileLearningStateModel, profile_id)
    items = (
        await db.scalars(
            select(LanguageItemModel)
            .where(
                LanguageItemModel.language_profile_id == profile_id,
            )
            .order_by(LanguageItemModel.introduced_at, LanguageItemModel.id)
        )
    ).all()
    eligible = await eligible_item_ids(db, profile_id, [item.id for item in items])
    rows = (
        await db.scalars(
            select(LearningOccurrenceModel)
            .join(
                LearningContributionModel,
                LearningContributionModel.analysis_run_id
                == LearningOccurrenceModel.analysis_run_id,
            )
            .where(
                LearningOccurrenceModel.language_profile_id == profile_id,
                LearningOccurrenceModel.kind != "introduction",
                LearningOccurrenceModel.suppressed_at.is_(None),
            )
            .order_by(
                LearningOccurrenceModel.occurred_at,
                LearningOccurrenceModel.session_id,
                LearningOccurrenceModel.ordinal,
            )
        )
    ).all()
    practices = tuple(
        PracticeOccurrence(
            row.id,
            row.session_id,
            row.occurred_at,
            row.lesson_key,
            row.capability_key or "",
            row.item_id,
            cast(Assistance, row.evidence["assistance"]),
            row.evidence.get("outcome") == "communicated"
            and row.evidence.get("opportunity_type") == "production",
        )
        for row in rows
        if (row.item_id is None or row.item_id in eligible)
        and all(
            UUID(str(item_id)) in eligible
            for item_id in cast(list[str], row.evidence.get("item_ids", []))
        )
    )
    benchmark_rows = (
        await db.scalars(
            select(LessonBenchmarkModel)
            .where(
                LessonBenchmarkModel.language_profile_id == profile_id,
            )
            .order_by(LessonBenchmarkModel.created_at, LessonBenchmarkModel.id)
        )
    ).all()
    benchmarks: list[LessonBenchmark] = []
    for row in benchmark_rows:
        result = TypeAdapter(DecisionsBenchmark).validate_python(row.distributions)
        threshold = float(cast(float, row.coverage.get("evidence_threshold", 0.8)))
        levels = int(cast(int, row.coverage.get("level_count", 4)))
        benchmarks.append(
            LessonBenchmark(
                row.lesson_key,
                row.content_version,
                row.rubric_version,
                row.history_revision,
                tuple(
                    _distribution(score, threshold, levels) for score in result.criterion_results
                ),
                _distribution(result.lesson_result, threshold, levels),
                row.complete,
            )
        )
    return ProfileProgress(
        profile_id,
        state.history_revision if state else 0,
        practices,
        tuple(
            RecallItem(
                item.id,
                profile_id,
                item.form,
                item.meaning,
                item.kind,
                tuple(item.capability_keys),
                item.introduced_session_id,
                item.introduced_at,
                item.id in eligible,
            )
            for item in items
        ),
        tuple(benchmarks),
        state.active_lesson_key if state else None,
    )
