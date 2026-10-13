"""Validate untrusted extraction candidates against finalized session turns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from mori.modules.learning.evidence import (
    AcceptedObservation,
    AnalysisContext,
    ObservationCandidate,
    validate_observation,
)

MIN_RECAP_OBSERVATION_CONFIDENCE = 0.7
MIN_INSIGHT_CONFIDENCE = 0.85
_SAFE_INSIGHT_TOPICS = {"interest", "occupation"}
_CONTACT_PATTERN = re.compile(r"(?:@|https?://|\b\+?\d[\d ()-]{7,}\d\b)", re.IGNORECASE)
_INTEREST_PATTERN = re.compile(
    r"\b(?:like|love|enjoy|interested in|gusta|aime|gosto)\b|喜欢|喜歡",
    re.IGNORECASE,
)
_OCCUPATION_PATTERN = re.compile(
    r"\b(?:i work as|i am a|i am an|i'm a|i'm an|my job is)\b|我(?:现在)?是|我做",
    re.IGNORECASE,
)
_NEGATED_INTEREST = (
    "don't like",
    "do not like",
    "dislike",
    "hate ",
    "no me gusta",
    "n'aime pas",
    "não gosto",
    "不喜欢",
    "不喜歡",
)
_UNSAFE_CONTEXT = ("if i ", "pretend", "imagine", "for example", "hypothetical", "假如", "如果")
_BROAD_VALUES = {"food", "travel", "music", "books", "film", "sports", "hobbies", "job", "work"}


@dataclass(frozen=True, slots=True)
class CorrectionCandidate:
    learner_turn_id: UUID
    suggestion: str


@dataclass(frozen=True, slots=True)
class InsightCandidate:
    fact: str
    source_turn_id: UUID
    source_quote: str
    topic: str
    confidence: float


@dataclass(frozen=True, slots=True)
class LearningCandidate:
    summary: str
    observations: tuple[ObservationCandidate, ...]
    corrections: tuple[CorrectionCandidate, ...]
    insights: tuple[InsightCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class PracticeCandidate:
    summary: str
    insights: tuple[InsightCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class FinalTurn:
    id: UUID
    sequence: int
    role: str
    text: str


@dataclass(frozen=True, slots=True)
class AcceptedCorrection:
    learner_turn_id: UUID
    suggestion: str


@dataclass(frozen=True, slots=True)
class AcceptedInsight:
    fact: str
    topic: str
    source_turn_id: UUID
    confidence: float


@dataclass(frozen=True, slots=True)
class ValidatedAnalysis:
    summary: str
    observations: tuple[AcceptedObservation, ...]
    corrections: tuple[AcceptedCorrection, ...]
    insights: tuple[AcceptedInsight, ...] = ()


def validate_candidate(
    candidate: LearningCandidate | PracticeCandidate,
    *,
    mode: str,
    turns: tuple[FinalTurn, ...],
    context: AnalysisContext | None = None,
) -> ValidatedAnalysis:
    if mode == "practice" and not isinstance(candidate, PracticeCandidate):
        raise ValueError("practice analysis has learning fields")
    if mode == "learning" and not isinstance(candidate, LearningCandidate):
        raise ValueError("learning analysis has no learning fields")
    summary = " ".join(candidate.summary.split())
    if not summary or len(summary) > 1000:
        raise ValueError("invalid recap summary")
    learner_ids = {turn.id for turn in turns if turn.role == "learner" and turn.text.strip()}
    learner_text = {turn.id: turn.text for turn in turns if turn.id in learner_ids}
    insights: list[AcceptedInsight] = []
    insight_keys: set[tuple[str, str]] = set()
    for insight in candidate.insights[:5]:
        value = " ".join(insight.fact.split()).strip(" .,!?:;")
        quote = " ".join(insight.source_quote.split())
        source = " ".join(learner_text.get(insight.source_turn_id, "").split())
        quote_folded = quote.casefold()
        marker = _INTEREST_PATTERN if insight.topic == "interest" else _OCCUPATION_PATTERN
        fact = f"Enjoys {value}." if insight.topic == "interest" else f"Works as {value}."
        key = (insight.topic, value.casefold())
        if (
            insight.topic not in _SAFE_INSIGHT_TOPICS
            or not value
            or len(value) < 3
            or value.casefold() in _BROAD_VALUES
            or len(fact) > 160
            or not quote
            or len(quote) > 200
            or quote.casefold() not in source.casefold()
            or value.casefold() not in quote_folded
            or marker.search(quote) is None
            or (
                insight.topic == "interest"
                and any(word in quote_folded for word in _NEGATED_INTEREST)
            )
            or any(word in quote_folded for word in _UNSAFE_CONTEXT)
            or _CONTACT_PATTERN.search(fact)
            or _CONTACT_PATTERN.search(quote)
            or key in insight_keys
            or not isfinite(insight.confidence)
            or not 0 <= insight.confidence <= 1
        ):
            continue
        if insight.confidence >= MIN_INSIGHT_CONFIDENCE:
            insights.append(
                AcceptedInsight(fact, insight.topic, insight.source_turn_id, insight.confidence)
            )
            insight_keys.add(key)
    if isinstance(candidate, PracticeCandidate):
        return ValidatedAnalysis(summary, (), (), tuple(insights))
    if context is None or context.lesson is None:
        raise ValueError("learning analysis requires pinned lesson context")
    if len(candidate.observations) > 3 or len(candidate.corrections) > 3:
        raise ValueError("too many analysis claims")
    observations: list[AcceptedObservation] = []
    for observation in candidate.observations:
        accepted = validate_observation(observation, lesson=context.lesson, turns=turns)
        if accepted.detail.casefold().startswith(("asked for", "requested", "produced a mandarin")):
            continue
        if observation.confidence < MIN_RECAP_OBSERVATION_CONFIDENCE:
            continue
        observations.append(accepted)
    corrections: list[AcceptedCorrection] = []
    for correction in candidate.corrections:
        suggestion = " ".join(correction.suggestion.split())
        if correction.learner_turn_id not in learner_ids or not suggestion or len(suggestion) > 240:
            raise ValueError("invalid or ungrounded correction")
        corrections.append(AcceptedCorrection(correction.learner_turn_id, suggestion))
    return ValidatedAnalysis(summary, tuple(observations), tuple(corrections), tuple(insights))
