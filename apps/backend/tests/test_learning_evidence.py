"""Practice provenance, semantic review gates, and provider request context."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mori.modules.curriculum.curriculum import FRAMEWORK_ID, LESSONS
from mori.modules.learning.domain import FinalTurn
from mori.modules.learning.evidence import (
    AnalysisContext,
    EvidenceCandidate,
    LessonContext,
    ObservationCandidate,
    ObservationReview,
    apply_observation_reviews,
    validate_observation,
)
from mori.modules.learning.extractor import (
    OpenAIExtractor,
    _LearningOutput,
    _ObservationReviewsOutput,
)
from mori.modules.learning.prompt import build_extraction_prompt

LESSON = LessonContext(LESSONS[0].key, LESSONS[0].label, LESSONS[0].guidance)
CONTEXT = AnalysisContext("english", "mandarin", FRAMEWORK_ID, LESSON)


def _candidate(learner: FinalTurn, tutor: FinalTurn | None = None) -> ObservationCandidate:
    return ObservationCandidate(
        "use",
        "Used 我喜欢 to express a personal interest.",
        0.9,
        LESSON.key,
        (
            EvidenceCandidate(
                learner.id,
                "我喜欢  排球",
                tutor.id if tutor else None,
                tutor.text if tutor else None,
                "independent",
            ),
        ),
    )


def test_preserves_exact_unicode_spans_and_the_preceding_opportunity() -> None:
    tutor = FinalTurn(uuid4(), 1, "tutor", "What activity do you enjoy?")
    learner = FinalTurn(uuid4(), 2, "learner", "嗯， 我喜欢  排球。")
    accepted = validate_observation(
        _candidate(learner, tutor), lesson=LESSON, turns=(tutor, learner)
    )
    occurrence = accepted.evidence[0]
    assert occurrence.learner.quote == "我喜欢  排球"
    assert (
        learner.text[occurrence.learner.start : occurrence.learner.end] == occurrence.learner.quote
    )
    assert occurrence.opportunity is not None
    assert occurrence.opportunity.turn_id == tutor.id
    assert occurrence.opportunity.quote == tutor.text
    assert occurrence.assistance == "independent"
    assert accepted.review_reason is None


@pytest.mark.parametrize("quote", ["我喜欢 排球", "我不喜欢排球", "", " "])
def test_rejects_normalized_or_fabricated_quotes(quote: str) -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "我喜欢  排球。")
    candidate = _candidate(learner)
    candidate = replace(candidate, evidence=(replace(candidate.evidence[0], learner_quote=quote),))
    with pytest.raises(ValueError, match="quote"):
        validate_observation(candidate, lesson=LESSON, turns=(learner,))


def test_repeated_quotes_require_a_unique_excerpt() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "我喜欢  排球。我喜欢  排球。")
    with pytest.raises(ValueError, match="ambiguous"):
        validate_observation(_candidate(learner), lesson=LESSON, turns=(learner,))


@pytest.mark.parametrize("role,sequence", [("learner", 1), ("tutor", 3)])
def test_opportunity_must_be_an_earlier_tutor_turn(role: str, sequence: int) -> None:
    opportunity = FinalTurn(uuid4(), sequence, role, "A question.")
    learner = FinalTurn(uuid4(), 2, "learner", "我喜欢  排球。")
    with pytest.raises(ValueError, match="opportunity"):
        validate_observation(
            _candidate(learner, opportunity), lesson=LESSON, turns=(opportunity, learner)
        )


def test_rejects_an_unpinned_curriculum_reference_and_duplicate_occurrences() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "我喜欢  排球。")
    candidate = _candidate(learner)
    with pytest.raises(ValueError, match="curriculum"):
        validate_observation(
            replace(candidate, curriculum_item_key=LESSONS[5].key), lesson=LESSON, turns=(learner,)
        )
    with pytest.raises(ValueError, match="learner evidence"):
        validate_observation(
            replace(candidate, evidence=candidate.evidence * 2), lesson=LESSON, turns=(learner,)
        )


def test_only_supported_semantic_reviews_survive() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "我喜欢  排球。")
    observation = validate_observation(_candidate(learner), lesson=LESSON, turns=(learner,))
    accepted = apply_observation_reviews(
        (observation, observation, observation),
        (
            ObservationReview(3, "uncertain", "Assistance cannot be determined."),
            ObservationReview(
                1, "supported", "The learner stated an interest without a supplied answer."
            ),
            ObservationReview(2, "unsupported", "The quoted content does not support the claim."),
        ),
    )
    assert len(accepted) == 1
    assert accepted[0].review_reason == "The learner stated an interest without a supplied answer."


@pytest.mark.parametrize(
    "reviews",
    [
        (),
        (ObservationReview(2, "supported", "A reason."),),
        (
            ObservationReview(1, "supported", "A reason."),
            ObservationReview(1, "supported", "Duplicate."),
        ),
        (ObservationReview(1, "supported", ""),),
    ],
)
def test_incomplete_or_malformed_reviews_fail_closed(
    reviews: tuple[ObservationReview, ...],
) -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "我喜欢  排球。")
    observation = validate_observation(_candidate(learner), lesson=LESSON, turns=(learner,))
    with pytest.raises(ValueError, match="review"):
        apply_observation_reviews((observation,), reviews)


@pytest.mark.asyncio
async def test_extractor_receives_languages_and_full_pinned_lesson(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "我喜欢  排球。")
    parsed = _LearningOutput.model_validate(
        {
            "summary": "Practiced expressing an interest.",
            "observations": [
                {
                    "kind": "use",
                    "detail": "Used 我喜欢 to express a personal interest.",
                    "confidence": 0.9,
                    "curriculum_item_key": LESSON.key,
                    "evidence": [
                        {
                            "learner_turn_id": str(learner.id),
                            "learner_quote": "我喜欢  排球",
                            "opportunity_turn_id": None,
                            "opportunity_quote": None,
                            "assistance": "independent",
                        }
                    ],
                }
            ],
            "corrections": [],
            "user_insights": [],
        }
    )
    provider = OpenAIExtractor("unused-test-key")
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))
    monkeypatch.setattr(provider._client.responses, "parse", parse)
    result = await provider.extract(
        mode="learning", model="fixture-model", context=CONTEXT, turns=(learner,)
    )
    request = parse.call_args.kwargs
    instructions = request["input"][0]["content"]
    assert '"base_language_id": "english"' in instructions
    assert '"target_language_id": "mandarin"' in instructions
    assert LESSON.key in instructions and LESSON.guidance in instructions
    assert request["store"] is False
    assert result.observations[0].evidence[0].learner_quote == "我喜欢  排球"


@pytest.mark.asyncio
async def test_semantic_reviewer_sees_full_transcript_and_can_reject_unrelated_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tutor = FinalTurn(uuid4(), 1, "tutor", "Try saying hello: 你好.")
    learner = FinalTurn(uuid4(), 2, "learner", "Hello.")
    candidate = ObservationCandidate(
        "use",
        "Independently used past tense to describe a holiday.",
        0.95,
        LESSON.key,
        (EvidenceCandidate(learner.id, "Hello.", tutor.id, tutor.text, "independent"),),
    )
    observation = validate_observation(candidate, lesson=LESSON, turns=(tutor, learner))
    parsed = _ObservationReviewsOutput.model_validate(
        {
            "reviews": [
                {
                    "ordinal": 1,
                    "decision": "unsupported",
                    "reason": "Hello does not express a past event.",
                }
            ]
        }
    )
    provider = OpenAIExtractor("unused-test-key")
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))
    monkeypatch.setattr(provider._client.responses, "parse", parse)
    reviews = await provider.review_observations(
        model="fixture-model",
        context=CONTEXT,
        turns=(tutor, learner),
        observations=(observation,),
    )
    request = parse.call_args.kwargs
    payload = json.loads(request["input"][1]["content"])
    assert payload["transcript"][0]["text"] == tutor.text
    assert payload["transcript"][1]["id"] == str(learner.id)
    assert payload["observations"][0]["evidence"][0]["learner"]["quote"] == "Hello."
    assert "Immediate copying" in request["input"][0]["content"]
    assert apply_observation_reviews((observation,), reviews) == ()
    assert request["store"] is False


@pytest.mark.asyncio
async def test_refused_review_cannot_accept_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "我喜欢  排球。")
    observation = validate_observation(_candidate(learner), lesson=LESSON, turns=(learner,))
    provider = OpenAIExtractor("unused-test-key")
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=None))
    monkeypatch.setattr(provider._client.responses, "parse", parse)
    with pytest.raises(ValueError, match="no structured evidence review"):
        await provider.review_observations(
            model="fixture-model", context=CONTEXT, turns=(learner,), observations=(observation,)
        )


def test_practice_extraction_cannot_include_a_lesson() -> None:
    with pytest.raises(ValueError, match="cannot have a lesson"):
        build_extraction_prompt(mode="practice", context=CONTEXT)
