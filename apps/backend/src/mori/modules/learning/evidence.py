"""Exact practice provenance and conservative semantic review decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from math import isfinite
from typing import Literal, Protocol
from uuid import UUID

from mori.modules.curriculum.domain import LessonDefinition

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
    lesson_definition: LessonDefinition | None = None
    known_items: tuple[KnownLanguageItem, ...] = ()
    language_profile_id: UUID | None = None
    session_id: UUID | None = None
    analysis_run_id: UUID | None = None
    user_id: UUID | None = None
    occurred_at: datetime | None = None
    learner_timezone: str | None = None


type LanguageItemKind = Literal["word", "phrase", "move"]
type PracticeOutcome = Literal["communicated", "not_yet", "uncertain"]
type OpportunityType = Literal["production", "recognition", "unknown"]


@dataclass(frozen=True, slots=True)
class KnownLanguageItem:
    id: UUID
    form: str
    meaning: str
    kind: LanguageItemKind
    capability_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntroductionCandidate:
    tutor_turn_id: UUID
    tutor_quote: str


@dataclass(frozen=True, slots=True)
class LanguageItemCandidate:
    key: str
    form: str
    meaning: str
    kind: LanguageItemKind
    capability_keys: tuple[str, ...]
    known_item_id: UUID | None = None
    introduction: IntroductionCandidate | None = None


@dataclass(frozen=True, slots=True)
class ItemPracticeCandidate:
    item_key: str
    evidence: EvidenceCandidate
    outcome: PracticeOutcome
    opportunity_type: OpportunityType


@dataclass(frozen=True, slots=True)
class CapabilityAttemptCandidate:
    capability_key: str
    evidence: EvidenceCandidate
    outcome: PracticeOutcome
    opportunity_type: OpportunityType
    item_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GroundedLanguageItem:
    key: str
    form: str
    meaning: str
    kind: LanguageItemKind
    capability_keys: tuple[str, ...]
    known_item_id: UUID | None
    introduction: QuotedTurn | None


@dataclass(frozen=True, slots=True)
class GroundedItemPractice:
    item_key: str
    evidence: PracticeEvidence
    outcome: PracticeOutcome
    opportunity_type: OpportunityType


@dataclass(frozen=True, slots=True)
class GroundedCapabilityAttempt:
    capability_key: str
    evidence: PracticeEvidence
    outcome: PracticeOutcome
    opportunity_type: OpportunityType
    item_keys: tuple[str, ...] = ()


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


def validate_source_quote(
    *, turn_id: UUID, quote: str, role: str, turns: tuple[EvidenceTurn, ...]
) -> QuotedTurn:
    turn = next((turn for turn in turns if turn.id == turn_id), None)
    if turn is None or turn.role != role:
        raise ValueError("invalid or ungrounded source turn")
    return _quoted_turn(turn, quote)


def _practice_evidence(
    candidate: EvidenceCandidate, *, context: AnalysisContext, turns: tuple[EvidenceTurn, ...]
) -> PracticeEvidence:
    assert context.lesson is not None
    return validate_observation(
        ObservationCandidate("use", "Grounded practice", 1.0, context.lesson.key, (candidate,)),
        lesson=context.lesson,
        turns=turns,
    ).evidence[0]


def validate_language_learning(
    *,
    context: AnalysisContext,
    turns: tuple[EvidenceTurn, ...],
    items: tuple[LanguageItemCandidate, ...],
    practices: tuple[ItemPracticeCandidate, ...],
    attempts: tuple[CapabilityAttemptCandidate, ...],
) -> tuple[
    tuple[GroundedLanguageItem, ...],
    tuple[GroundedItemPractice, ...],
    tuple[GroundedCapabilityAttempt, ...],
]:
    """Ground claims without making semantic or advancement decisions."""
    if len(items) > 12 or len(practices) > 40 or len(attempts) > 24:
        raise ValueError("too many structured learning claims")
    if not (items or practices or attempts):
        return (), (), ()
    definition = context.lesson_definition
    if definition is None or context.lesson is None or definition.lesson_key != context.lesson.key:
        raise ValueError("structured learning requires a pinned lesson definition")
    allowed = set(definition.capability_keys)
    known = {item.id: item for item in context.known_items}
    if len(known) != len(context.known_items):
        raise ValueError("duplicate known language item")
    grounded_items: list[GroundedLanguageItem] = []
    by_key: dict[str, GroundedLanguageItem] = {}
    known_ids: set[UUID] = set()
    for item in items:
        if (
            not item.key
            or len(item.key) > 64
            or item.key != item.key.strip()
            or item.key in by_key
            or not item.form.strip()
            or len(item.form) > 160
            or item.form != item.form.strip()
            or not item.meaning.strip()
            or len(item.meaning) > 240
            or item.kind not in {"word", "phrase", "move"}
            or len(set(item.capability_keys)) != len(item.capability_keys)
            or any(key not in allowed for key in item.capability_keys)
        ):
            raise ValueError("invalid language item or capability reference")
        if item.known_item_id is not None:
            existing = known.get(item.known_item_id)
            if (
                existing is None
                or item.known_item_id in known_ids
                or (item.form, item.meaning, item.kind)
                != (existing.form, existing.meaning, existing.kind)
            ):
                raise ValueError("language item does not match known owned item")
            known_ids.add(item.known_item_id)
        introduction = (
            validate_source_quote(
                turn_id=item.introduction.tutor_turn_id,
                quote=item.introduction.tutor_quote,
                role="tutor",
                turns=turns,
            )
            if item.introduction
            else None
        )
        grounded = GroundedLanguageItem(
            item.key,
            item.form,
            item.meaning,
            item.kind,
            item.capability_keys,
            item.known_item_id,
            introduction,
        )
        by_key[item.key] = grounded
        grounded_items.append(grounded)
    grounded_practices: list[GroundedItemPractice] = []
    seen_practices: set[tuple[str, UUID, int, int]] = set()
    for practice in practices:
        if (
            practice.item_key not in by_key
            or practice.outcome not in {"communicated", "not_yet", "uncertain"}
            or practice.opportunity_type not in {"production", "recognition", "unknown"}
        ):
            raise ValueError("invalid item practice")
        evidence = _practice_evidence(practice.evidence, context=context, turns=turns)
        key = (
            practice.item_key,
            evidence.learner.turn_id,
            evidence.learner.start,
            evidence.learner.end,
        )
        if key in seen_practices:
            raise ValueError("duplicate item practice")
        seen_practices.add(key)
        grounded_practices.append(
            GroundedItemPractice(
                practice.item_key,
                evidence,
                practice.outcome,
                practice.opportunity_type,
            )
        )
    practiced = {practice.item_key for practice in practices}
    if any(item.introduction is None and item.key not in practiced for item in grounded_items):
        raise ValueError("language item has no teaching or practice evidence")
    grounded_attempts: list[GroundedCapabilityAttempt] = []
    seen_attempts: set[tuple[str, UUID, int, int]] = set()
    for attempt in attempts:
        if (
            attempt.capability_key not in allowed
            or attempt.outcome not in {"communicated", "not_yet", "uncertain"}
            or attempt.opportunity_type not in {"production", "recognition", "unknown"}
            or len(set(attempt.item_keys)) != len(attempt.item_keys)
            or any(key not in by_key for key in attempt.item_keys)
        ):
            raise ValueError("invalid capability attempt")
        evidence = _practice_evidence(attempt.evidence, context=context, turns=turns)
        key = (
            attempt.capability_key,
            evidence.learner.turn_id,
            evidence.learner.start,
            evidence.learner.end,
        )
        if key in seen_attempts:
            raise ValueError("duplicate capability attempt")
        seen_attempts.add(key)
        grounded_attempts.append(
            GroundedCapabilityAttempt(
                attempt.capability_key,
                evidence,
                attempt.outcome,
                attempt.opportunity_type,
                attempt.item_keys,
            )
        )
    return tuple(grounded_items), tuple(grounded_practices), tuple(grounded_attempts)


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
