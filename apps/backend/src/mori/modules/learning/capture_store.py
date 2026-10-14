"""Transactional structured contributions and immutable benchmark evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mori.modules.learning.decisions import CurrentEvidenceReview, LessonBenchmark
from mori.modules.learning.domain import ValidatedAnalysis
from mori.modules.learning.evidence import AnalysisContext, PracticeEvidence
from mori.modules.learning.models import (
    AnalysisDecisionReviewModel,
    AnalysisRunModel,
    LanguageItemModel,
    LearnerFileEntryModel,
    LearningContributionModel,
    LearningOccurrenceModel,
    LessonBenchmarkModel,
    ProfileLearningStateModel,
    UserInsightModel,
)
from mori.modules.learning.progress_store import json_record
from mori.modules.learning.user_insights import insight_identity
from mori.modules.sessions.models import SessionModel


async def lock_profile_state(db: AsyncSession, profile_id: UUID) -> ProfileLearningStateModel:
    # Callers hold the owning account lock first, making first-state creation safe.
    state = await db.scalar(
        select(ProfileLearningStateModel)
        .where(
            ProfileLearningStateModel.language_profile_id == profile_id,
        )
        .with_for_update()
    )
    if state is None:
        state = ProfileLearningStateModel(
            language_profile_id=profile_id, history_revision=0, updated_at=datetime.now(UTC)
        )
        db.add(state)
        await db.flush()
    return state


async def commit_contribution(
    db: AsyncSession,
    *,
    session: SessionModel,
    run: AnalysisRunModel,
    context: AnalysisContext,
    analysis: ValidatedAnalysis,
    state: ProfileLearningStateModel,
    review: CurrentEvidenceReview | None,
) -> ValidatedAnalysis:
    now = datetime.now(UTC)
    occurrence_time = context.occurred_at or session.created_at
    lesson_key = context.lesson.key if context.lesson else "conversation-practice"
    content_version = (
        context.lesson_definition.content_version
        if context.lesson_definition
        else run.curriculum_version
    )
    items = []
    item_ids: dict[str, UUID] = {}
    for item in analysis.language_items:
        record = await db.get(LanguageItemModel, item.known_item_id) if item.known_item_id else None
        if record is not None and record.language_profile_id != session.language_profile_id:
            raise ValueError("language item crosses profiles")
        if item.known_item_id is not None and record is None:
            raise ValueError("known language item is missing")
        if record is None:
            record = await db.scalar(
                select(LanguageItemModel)
                .where(
                    LanguageItemModel.language_profile_id == session.language_profile_id,
                    LanguageItemModel.form == item.form,
                    LanguageItemModel.meaning == item.meaning,
                    LanguageItemModel.kind == item.kind,
                    LanguageItemModel.capability_keys == list(item.capability_keys),
                )
                .order_by(LanguageItemModel.introduced_at, LanguageItemModel.id)
                .limit(1)
            )
        if record is None:
            record = LanguageItemModel(
                id=uuid4(),
                language_profile_id=session.language_profile_id,
                form=item.form,
                meaning=item.meaning,
                kind=item.kind,
                capability_keys=list(item.capability_keys),
                introduced_session_id=session.id,
                introduced_at=occurrence_time,
            )
            db.add(record)
            await db.flush()
        projection = await db.scalar(
            select(LearnerFileEntryModel.id)
            .where(
                LearnerFileEntryModel.language_item_id == record.id,
                LearnerFileEntryModel.deleted_at.is_(None),
            )
            .limit(1)
        )
        if projection is None and record.suppressed_at is None:
            db.add(
                LearnerFileEntryModel(
                    id=uuid4(),
                    language_item_id=record.id,
                    language_profile_id=session.language_profile_id,
                    source_session_id=session.id,
                    kind="learning",
                    text=f"{item.form} - {item.meaning}"[:240],
                    origin="capture",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
        item_ids[item.key] = record.id
        items.append(replace(item, known_item_id=record.id))
    analysis = replace(analysis, language_items=tuple(items))
    ordinal = 0

    def occurrence(
        kind: str, item_id: UUID | None, capability_key: str | None, evidence: dict[str, object]
    ) -> None:
        nonlocal ordinal
        ordinal += 1
        db.add(
            LearningOccurrenceModel(
                id=uuid4(),
                language_profile_id=session.language_profile_id,
                session_id=session.id,
                analysis_run_id=run.id,
                ordinal=ordinal,
                lesson_key=lesson_key,
                kind=kind,
                item_id=item_id,
                capability_key=capability_key,
                occurred_at=occurrence_time,
                evidence=evidence,
            )
        )

    def practice_record(
        evidence: PracticeEvidence, outcome: str, opportunity_type: str
    ) -> dict[str, object]:
        result = json_record(evidence)
        result.update({"outcome": outcome, "opportunity_type": opportunity_type})
        return result

    for item in analysis.language_items:
        if item.introduction is not None:
            occurrence("introduction", item_ids[item.key], None, json_record(item.introduction))
    for practice in analysis.item_practices:
        occurrence(
            "item_practice",
            item_ids[practice.item_key],
            None,
            practice_record(practice.evidence, practice.outcome, practice.opportunity_type),
        )
    for attempt in analysis.capability_attempts:
        occurrence(
            "capability_attempt",
            None,
            attempt.capability_key,
            {
                **practice_record(attempt.evidence, attempt.outcome, attempt.opportunity_type),
                "item_ids": [str(item_ids[key]) for key in attempt.item_keys],
            },
        )
    state.history_revision += 1
    state.updated_at = now
    contribution = await db.get(LearningContributionModel, session.id)
    data = json_record(replace(analysis, insights=(), user_insights=()))
    if contribution is None:
        db.add(
            LearningContributionModel(
                session_id=session.id,
                language_profile_id=session.language_profile_id,
                analysis_run_id=run.id,
                history_revision=state.history_revision,
                occurred_at=occurrence_time,
                lesson_key=lesson_key,
                content_version=content_version,
                accepted_analysis=data,
            )
        )
    else:
        contribution.analysis_run_id = run.id
        contribution.history_revision = state.history_revision
        contribution.accepted_analysis = data
        contribution.content_version = content_version
        contribution.lesson_key = lesson_key
    if review is not None:
        db.add(AnalysisDecisionReviewModel(analysis_run_id=run.id, payload=json_record(review)))
    return analysis


def store_benchmark(
    db: AsyncSession,
    *,
    context: AnalysisContext,
    benchmark: LessonBenchmark,
    applicability_revision: int,
    source_run_id: UUID,
    evidence_threshold: float,
) -> None:
    definition = context.lesson_definition
    if definition is None or definition.rubric is None or context.language_profile_id is None:
        raise ValueError("benchmark has no pinned lesson")
    if (
        benchmark.lesson_key != definition.lesson_key
        or benchmark.content_version != definition.content_version
        or benchmark.rubric_version != definition.rubric.version
        or benchmark.current_session_id != context.session_id
        or source_run_id not in benchmark.source_analysis_ids
    ):
        raise ValueError("benchmark bundle does not match pinned analysis")
    db.add(
        LessonBenchmarkModel(
            id=uuid4(),
            language_profile_id=context.language_profile_id,
            source_analysis_run_id=source_run_id,
            lesson_key=benchmark.lesson_key,
            content_version=benchmark.content_version,
            rubric_version=benchmark.rubric_version,
            history_revision=applicability_revision,
            complete=benchmark.complete,
            coverage={
                "input_revision": benchmark.history_revision,
                "history_digest": benchmark.history_digest,
                "source_analysis_ids": [str(value) for value in benchmark.source_analysis_ids],
                "evidence_threshold": evidence_threshold,
                "level_count": len(definition.rubric.levels),
            },
            distributions=json_record(benchmark),
            created_at=datetime.now(UTC),
        )
    )


async def capture_user_insights(
    db: AsyncSession, *, session: SessionModel, analysis: ValidatedAnalysis
) -> None:
    now = datetime.now(UTC)
    for insight in analysis.user_insights:
        digest = insight_identity(session.user_id, insight.text, insight.temporal_context)
        exists = await db.scalar(
            select(UserInsightModel.id)
            .where(
                UserInsightModel.user_id == session.user_id,
                or_(
                    UserInsightModel.identity_digest == digest,
                    UserInsightModel.edited_identity_digest == digest,
                    UserInsightModel.suppressed_identity_digests.contains([digest]),
                ),
            )
            .limit(1)
        )
        if exists is not None:
            continue
        db.add(
            UserInsightModel(
                id=uuid4(),
                user_id=session.user_id,
                source_session_id=session.id,
                source_turn_id=insight.source.turn_id,
                source_quote=insight.source.quote,
                source_quote_start=insight.source.start,
                source_quote_end=insight.source.end,
                temporal_context=insight.temporal_context,
                identity_digest=digest,
                text=insight.text,
                origin="capture",
                version=1,
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(days=90),
            )
        )
