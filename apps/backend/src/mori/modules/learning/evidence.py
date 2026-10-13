"""Exact practice provenance and conservative semantic review decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from typing import Literal, Protocol
from uuid import UUID

type Assistance = Literal["independent", "cued", "modelled", "unknown"]
type ReviewDecision = Literal["supported", "unsupported", "uncertain"]


@dataclass(frozen=True, slots=True)
class LessonContext:
    key: str
    label: str
    guidance: str


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    base_language_id: str
    target_language_id: str
    curriculum_version: str
    lesson: LessonContext | None


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    learner_turn_id: UUID
    learner_quote: str
    opportunity_turn_id: UUID | None
    opportunity_quote: str | None
    assistance: Assistance


@dataclass(frozen=True, slots=True)
class ObservationCandidate:
    kind: str
    detail: str
    confidence: float
    curriculum_item_key: str
    evidence: tuple[EvidenceCandidate, ...]


@dataclass(frozen=True, slots=True)
class QuotedTurn:
    turn_id: UUID
    quote: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PracticeEvidence:
    learner: QuotedTurn
    opportunity: QuotedTurn | None
    assistance: Assistance


@dataclass(frozen=True, slots=True)
class AcceptedObservation:
    kind: str
    detail: str
    confidence: float
    curriculum_item_key: str
    evidence: tuple[PracticeEvidence, ...]
    review_reason: str | None = None

    @property
    def learner_turn_ids(self) -> tuple[UUID, ...]:
        return tuple(item.learner.turn_id for item in self.evidence)


@dataclass(frozen=True, slots=True)
class ObservationReview:
    ordinal: int
    decision: ReviewDecision
    reason: str


class EvidenceTurn(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def sequence(self) -> int: ...

    @property
    def role(self) -> str: ...

    @property
    def text(self) -> str: ...


def _quoted_turn(turn: EvidenceTurn, quote: str) -> QuotedTurn:
    # Preserve exact Unicode text. Ambiguous excerpts need more surrounding words.
    if not quote or not quote.strip() or len(quote) > 200:
        raise ValueError("invalid evidence quote")
    start = turn.text.find(quote)
    if start < 0 or turn.text.find(quote, start + 1) >= 0:
        raise ValueError("ungrounded or ambiguous evidence quote")
    return QuotedTurn(turn.id, quote, start, start + len(quote))


def validate_observation(
    candidate: ObservationCandidate,
    *,
    lesson: LessonContext,
    turns: tuple[EvidenceTurn, ...],
) -> AcceptedObservation:
    detail = " ".join(candidate.detail.split())
    if (
        candidate.kind not in {"use", "comprehension", "repair", "vocabulary", "concept"}
        or not detail
        or len(detail) > 240
        or candidate.curriculum_item_key != lesson.key
        or not 1 <= len(candidate.evidence) <= 5
        or not isfinite(candidate.confidence)
        or not 0 <= candidate.confidence <= 1
    ):
        raise ValueError("invalid observation or curriculum reference")
    by_id = {turn.id: turn for turn in turns}
    evidence: list[PracticeEvidence] = []
    seen: set[UUID] = set()
    for item in candidate.evidence:
        learner = by_id.get(item.learner_turn_id)
        if (
            learner is None
            or learner.role != "learner"
            or learner.id in seen
            or item.assistance not in {"independent", "cued", "modelled", "unknown"}
        ):
            raise ValueError("invalid or ungrounded learner evidence")
        learner_span = _quoted_turn(learner, item.learner_quote)
        opportunity_span = None
        if item.opportunity_turn_id is None:
            if item.opportunity_quote is not None:
                raise ValueError("opportunity quote has no turn")
        else:
            opportunity = by_id.get(item.opportunity_turn_id)
            if (
                opportunity is None
                or opportunity.role != "tutor"
                or opportunity.sequence >= learner.sequence
                or item.opportunity_quote is None
            ):
                raise ValueError("invalid or ungrounded practice opportunity")
            opportunity_span = _quoted_turn(opportunity, item.opportunity_quote)
        evidence.append(PracticeEvidence(learner_span, opportunity_span, item.assistance))
        seen.add(learner.id)
    return AcceptedObservation(
        candidate.kind, detail, candidate.confidence, lesson.key, tuple(evidence)
    )


def apply_observation_reviews(
    observations: tuple[AcceptedObservation, ...], reviews: tuple[ObservationReview, ...]
) -> tuple[AcceptedObservation, ...]:
    expected = set(range(1, len(observations) + 1))
    if len(reviews) != len(expected) or {review.ordinal for review in reviews} != expected:
        raise ValueError("incomplete or duplicate evidence review")
    by_ordinal = {review.ordinal: review for review in reviews}
    accepted: list[AcceptedObservation] = []
    for ordinal, observation in enumerate(observations, 1):
        review = by_ordinal[ordinal]
        reason = " ".join(review.reason.split())
        if review.decision not in {"supported", "unsupported", "uncertain"} or (
            not reason or len(reason) > 240
        ):
            raise ValueError("invalid evidence review")
        if review.decision == "supported":
            accepted.append(replace(observation, review_reason=reason))
    return tuple(accepted)
