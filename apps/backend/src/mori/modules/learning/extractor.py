"""Mode-specific extraction and a separate review of learning claims."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Literal, Protocol
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field

from mori.modules.learning.domain import (
    CorrectionCandidate,
    FinalTurn,
    LearningCandidate,
    PracticeCandidate,
    UserInsightCandidate,
)
from mori.modules.learning.evidence import (
    AcceptedObservation,
    AnalysisContext,
    Assistance,
    CapabilityAttemptCandidate,
    EvidenceCandidate,
    IntroductionCandidate,
    ItemPracticeCandidate,
    LanguageItemCandidate,
    LanguageItemKind,
    ObservationCandidate,
    ObservationReview,
    OpportunityType,
    PracticeOutcome,
    ReviewDecision,
)
from mori.modules.learning.prompt import build_evidence_review_prompt, build_extraction_prompt


class _EvidenceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    learner_turn_id: str
    learner_quote: str
    opportunity_turn_id: str | None
    opportunity_quote: str | None
    assistance: Assistance


class _ObservationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["use", "comprehension", "repair", "vocabulary", "concept"]
    detail: str
    confidence: float
    curriculum_item_key: str
    evidence: list[_EvidenceOutput]


class _ReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    decision: ReviewDecision
    reason: str


class _ObservationReviewsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviews: list[_ReviewOutput]


class _CorrectionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    learner_turn_id: str
    suggestion: str


class _UserInsightOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_turn_id: str
    source_quote: str
    text: str = Field(min_length=1, max_length=120)
    temporal_context: str | None


class _IntroductionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tutor_turn_id: str
    tutor_quote: str


class _LanguageItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    form: str
    meaning: str
    kind: LanguageItemKind
    capability_keys: list[str]
    known_item_id: str | None
    introduction: _IntroductionOutput | None


class _ItemPracticeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_key: str
    evidence: _EvidenceOutput
    outcome: PracticeOutcome
    opportunity_type: OpportunityType


class _CapabilityAttemptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_key: str
    evidence: _EvidenceOutput
    outcome: PracticeOutcome
    opportunity_type: OpportunityType
    item_keys: list[str]


class _LearningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    observations: list[_ObservationOutput]
    corrections: list[_CorrectionOutput]
    user_insights: list[_UserInsightOutput] = Field(default_factory=list, max_length=2)
    language_items: list[_LanguageItemOutput] = Field(default_factory=list, max_length=12)
    item_practices: list[_ItemPracticeOutput] = Field(default_factory=list, max_length=40)
    capability_attempts: list[_CapabilityAttemptOutput] = Field(default_factory=list, max_length=24)


class _PracticeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    user_insights: list[_UserInsightOutput] = Field(default_factory=list, max_length=2)


def _insights(outputs: list[_UserInsightOutput]) -> tuple[UserInsightCandidate, ...]:
    return tuple(
        UserInsightCandidate(
            text=item.text,
            source_turn_id=UUID(item.source_turn_id),
            source_quote=item.source_quote,
            temporal_context=item.temporal_context,
        )
        for item in outputs
    )


def _evidence(item: _EvidenceOutput) -> EvidenceCandidate:
    return EvidenceCandidate(
        UUID(item.learner_turn_id),
        item.learner_quote,
        UUID(item.opportunity_turn_id) if item.opportunity_turn_id is not None else None,
        item.opportunity_quote,
        item.assistance,
    )


class Extractor(Protocol):
    async def extract(
        self, *, mode: str, model: str, context: AnalysisContext, turns: tuple[FinalTurn, ...]
    ) -> LearningCandidate | PracticeCandidate: ...

    async def review_observations(
        self,
        *,
        model: str,
        context: AnalysisContext,
        turns: tuple[FinalTurn, ...],
        observations: tuple[AcceptedObservation, ...],
    ) -> tuple[ObservationReview, ...]: ...


class OpenAIExtractor:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

    async def extract(
        self, *, mode: str, model: str, context: AnalysisContext, turns: tuple[FinalTurn, ...]
    ) -> LearningCandidate | PracticeCandidate:
        transcript = json.dumps(
            [{"id": str(turn.id), "speaker": turn.role, "text": turn.text} for turn in turns],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        instructions = build_extraction_prompt(mode=mode, context=context)
        if mode == "learning":
            learning_response = await self._client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": transcript},
                ],
                text_format=_LearningOutput,
                store=False,
            )
            if learning_response.output_parsed is None:
                raise ValueError("extractor returned no structured analysis")
            output = learning_response.output_parsed
            return LearningCandidate(
                summary=output.summary,
                observations=tuple(
                    ObservationCandidate(
                        kind=o.kind,
                        detail=o.detail,
                        confidence=o.confidence,
                        curriculum_item_key=o.curriculum_item_key,
                        evidence=tuple(_evidence(item) for item in o.evidence),
                    )
                    for o in output.observations
                ),
                corrections=tuple(
                    CorrectionCandidate(UUID(c.learner_turn_id), c.suggestion)
                    for c in output.corrections
                ),
                user_insights=_insights(output.user_insights),
                language_items=tuple(
                    LanguageItemCandidate(
                        item.key,
                        item.form,
                        item.meaning,
                        item.kind,
                        tuple(item.capability_keys),
                        UUID(item.known_item_id) if item.known_item_id is not None else None,
                        IntroductionCandidate(
                            UUID(item.introduction.tutor_turn_id),
                            item.introduction.tutor_quote,
                        )
                        if item.introduction is not None
                        else None,
                    )
                    for item in output.language_items
                ),
                item_practices=tuple(
                    ItemPracticeCandidate(
                        item.item_key,
                        _evidence(item.evidence),
                        item.outcome,
                        item.opportunity_type,
                    )
                    for item in output.item_practices
                ),
                capability_attempts=tuple(
                    CapabilityAttemptCandidate(
                        item.capability_key,
                        _evidence(item.evidence),
                        item.outcome,
                        item.opportunity_type,
                        tuple(item.item_keys),
                    )
                    for item in output.capability_attempts
                ),
            )
        practice_response = await self._client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": transcript},
            ],
            text_format=_PracticeOutput,
            store=False,
        )
        if practice_response.output_parsed is None:
            raise ValueError("extractor returned no structured analysis")
        return PracticeCandidate(
            summary=practice_response.output_parsed.summary,
            user_insights=_insights(practice_response.output_parsed.user_insights),
        )

    async def review_observations(
        self,
        *,
        model: str,
        context: AnalysisContext,
        turns: tuple[FinalTurn, ...],
        observations: tuple[AcceptedObservation, ...],
    ) -> tuple[ObservationReview, ...]:
        if not observations:
            return ()
        payload = json.dumps(
            {
                "transcript": [asdict(turn) for turn in turns],
                "observations": [
                    {"ordinal": ordinal, **asdict(observation)}
                    for ordinal, observation in enumerate(observations, 1)
                ],
            },
            default=str,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = await self._client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": build_evidence_review_prompt(context=context)},
                {"role": "user", "content": payload},
            ],
            text_format=_ObservationReviewsOutput,
            store=False,
        )
        if response.output_parsed is None:
            raise ValueError("reviewer returned no structured evidence review")
        return tuple(
            ObservationReview(item.ordinal, item.decision, item.reason)
            for item in response.output_parsed.reviews
        )
