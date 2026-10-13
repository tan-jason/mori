"""Mode-specific extraction and a separate review of learning claims."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Literal, Protocol
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict

from mori.modules.learning.domain import (
    CorrectionCandidate,
    FinalTurn,
    InsightCandidate,
    LearningCandidate,
    PracticeCandidate,
)
from mori.modules.learning.evidence import (
    AcceptedObservation,
    AnalysisContext,
    Assistance,
    EvidenceCandidate,
    ObservationCandidate,
    ObservationReview,
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


class _InsightOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_turn_id: str
    source_quote: str
    category: Literal["interest", "occupation"]
    value: str
    confidence: float


class _LearningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    observations: list[_ObservationOutput]
    corrections: list[_CorrectionOutput]
    insights: list[_InsightOutput]


class _PracticeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    insights: list[_InsightOutput]


def _insights(outputs: list[_InsightOutput]) -> tuple[InsightCandidate, ...]:
    return tuple(
        InsightCandidate(
            fact=item.value,
            source_turn_id=UUID(item.source_turn_id),
            source_quote=item.source_quote,
            topic=item.category,
            confidence=item.confidence,
        )
        for item in outputs
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
                        evidence=tuple(
                            EvidenceCandidate(
                                UUID(item.learner_turn_id),
                                item.learner_quote,
                                UUID(item.opportunity_turn_id)
                                if item.opportunity_turn_id is not None
                                else None,
                                item.opportunity_quote,
                                item.assistance,
                            )
                            for item in o.evidence
                        ),
                    )
                    for o in output.observations
                ),
                corrections=tuple(
                    CorrectionCandidate(UUID(c.learner_turn_id), c.suggestion)
                    for c in output.corrections
                ),
                insights=_insights(output.insights),
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
            insights=_insights(practice_response.output_parsed.insights),
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
