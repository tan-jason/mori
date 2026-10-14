"""Synthetic language evidence, conservative Decisions gates, and full-history rubrics."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from openai.types.decision import Decision
from openai.types.decision_create_params import Question
from pydantic import ValidationError

from mori.modules.curriculum.catalog import CodeCourseCatalog, published_lesson_definition
from mori.modules.curriculum.curriculum import (
    BEGINNER_LESSON_DEFINITIONS,
    FRAMEWORK_ID,
    LESSONS,
    PART1_FRAMEWORK_ID,
)
from mori.modules.learning.decisions import (
    HistoricalLearningRecord,
    LearningHistory,
    OpenAIDecisionsReviewer,
    validate_decision_response,
)
from mori.modules.learning.domain import (
    FinalTurn,
    LearningCandidate,
    PracticeCandidate,
    UserInsightCandidate,
    validate_candidate,
)
from mori.modules.learning.evidence import (
    AnalysisContext,
    CapabilityAttemptCandidate,
    EvidenceCandidate,
    IntroductionCandidate,
    ItemPracticeCandidate,
    KnownLanguageItem,
    LanguageItemCandidate,
    LessonContext,
)
from mori.modules.learning.extractor import OpenAIExtractor, _LearningOutput
from mori.modules.learning.prompt import build_extraction_prompt

PROFILE_ID = uuid4()
SESSION_ID = uuid4()
ANALYSIS_ID = uuid4()
CONTEXT = AnalysisContext(
    "english",
    "mandarin",
    FRAMEWORK_ID,
    LessonContext(LESSONS[0].key, LESSONS[0].label, LESSONS[0].guidance),
    lesson_definition=BEGINNER_LESSON_DEFINITIONS[0],
    language_profile_id=PROFILE_ID,
    session_id=SESSION_ID,
    analysis_run_id=ANALYSIS_ID,
    occurred_at=datetime(2026, 10, 13, tzinfo=UTC),
)


def _practice():  # type: ignore[no-untyped-def]
    tutor = FinalTurn(uuid4(), 1, "tutor", "Say 我喜欢 to express what you like.")
    learner = FinalTurn(uuid4(), 2, "learner", "我喜欢排球。")
    evidence = EvidenceCandidate(learner.id, learner.text, tutor.id, tutor.text, "modelled")
    item = LanguageItemCandidate(
        "like-frame",
        "我喜欢",
        "I like",
        "phrase",
        ("express-detail",),
        introduction=IntroductionCandidate(tutor.id, tutor.text),
    )
    candidate = LearningCandidate(
        "Practiced expressing an interest.",
        (),
        (),
        language_items=(item,),
        item_practices=(ItemPracticeCandidate(item.key, evidence, "communicated", "production"),),
        capability_attempts=(
            CapabilityAttemptCandidate(
                "express-detail",
                evidence,
                "communicated",
                "production",
                (item.key,),
            ),
        ),
    )
    return tutor, learner, candidate


def _decision(answers: list[dict[str, object]]) -> Decision:
    return Decision.model_validate(
        {
            "model": "gpt-6-luna",
            "answers": answers,
            "usage": {
                "input_tokens": 1,
                "output_tokens": 0,
                "total_tokens": 1,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }
    )


def _answers(questions: tuple[Question, ...]) -> list[dict[str, object]]:
    answers: list[dict[str, object]] = []
    for question in questions:
        if question["type"] == "predicate":
            answers.append({"type": "predicate", "name": question["name"], "probability": 0.9})
        elif question["type"] == "score":
            levels = tuple(question["levels"])
            probabilities = (0.0, 0.1, 0.4, 0.5)
            answers.append(
                {
                    "type": "score",
                    "name": question["name"],
                    "score": 2.4,
                    "confidence": 0.5,
                    "probabilities": [
                        {
                            "value": index,
                            "label": level["label"],
                            "probability": probabilities[index],
                        }
                        for index, level in enumerate(levels)
                    ],
                }
            )
    return answers


def test_grounded_items_preserve_supported_first_practice_and_real_language() -> None:
    tutor, learner, candidate = _practice()
    analysis = validate_candidate(
        candidate, mode="learning", context=CONTEXT, turns=(tutor, learner)
    )
    assert analysis.language_items[0].introduction is not None
    assert analysis.language_items[0].form == "我喜欢"
    assert analysis.item_practices[0].evidence.assistance == "modelled"
    assert analysis.capability_attempts[0].capability_key == "express-detail"
    assert not hasattr(analysis.item_practices[0], "recurring_help")


def test_introduction_without_learner_attempt_is_exposure() -> None:
    tutor, learner, candidate = _practice()
    candidate = replace(candidate, item_practices=(), capability_attempts=())
    analysis = validate_candidate(
        candidate, mode="learning", context=CONTEXT, turns=(tutor, learner)
    )
    assert len(analysis.language_items) == 1
    assert analysis.item_practices == analysis.capability_attempts == ()


def test_independence_is_not_success_and_recognition_is_not_production() -> None:
    tutor, learner, candidate = _practice()
    evidence = replace(candidate.item_practices[0].evidence, assistance="independent")
    candidate = replace(
        candidate,
        item_practices=(
            replace(
                candidate.item_practices[0],
                evidence=evidence,
                outcome="not_yet",
                opportunity_type="recognition",
            ),
        ),
    )
    analysis = validate_candidate(
        candidate, mode="learning", context=CONTEXT, turns=(tutor, learner)
    )
    assert analysis.item_practices[0].outcome == "not_yet"
    assert analysis.item_practices[0].opportunity_type == "recognition"


def test_unknown_owned_items_and_unpinned_capabilities_fail_closed() -> None:
    tutor, learner, candidate = _practice()
    bad_item = replace(candidate.language_items[0], known_item_id=uuid4())
    with pytest.raises(ValueError, match="owned item"):
        validate_candidate(
            replace(candidate, language_items=(bad_item,)),
            mode="learning",
            context=CONTEXT,
            turns=(tutor, learner),
        )
    bad_attempt = replace(candidate.capability_attempts[0], capability_key="invented-capability")
    with pytest.raises(ValueError, match="capability attempt"):
        validate_candidate(
            replace(candidate, capability_attempts=(bad_attempt,)),
            mode="learning",
            context=CONTEXT,
            turns=(tutor, learner),
        )
    with pytest.raises(ValueError, match="duplicate capability"):
        validate_candidate(
            replace(candidate, capability_attempts=candidate.capability_attempts * 2),
            mode="learning",
            context=CONTEXT,
            turns=(tutor, learner),
        )


def test_known_repertoire_cannot_be_reidentified_as_a_synonym() -> None:
    tutor, learner, candidate = _practice()
    known = KnownLanguageItem(uuid4(), "我喜欢", "I like", "phrase", ("express-detail",))
    context = replace(CONTEXT, known_items=(known,))
    item = replace(candidate.language_items[0], known_item_id=known.id)
    validate_candidate(
        replace(candidate, language_items=(item,)),
        mode="learning",
        context=context,
        turns=(tutor, learner),
    )
    with pytest.raises(ValueError, match="known owned item"):
        validate_candidate(
            replace(candidate, language_items=(replace(item, form="我爱"),)),
            mode="learning",
            context=context,
            turns=(tutor, learner),
        )


def test_collection_bounds_detect_overruns_without_truncation() -> None:
    tutor, learner, candidate = _practice()
    items = tuple(replace(candidate.language_items[0], key=f"item-{index}") for index in range(13))
    with pytest.raises(ValueError, match="too many structured"):
        validate_candidate(
            replace(candidate, language_items=items),
            mode="learning",
            context=CONTEXT,
            turns=(tutor, learner),
        )


def test_optional_category_free_insights_are_exact_short_facts() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "I moved to a new city last spring.")
    insight = UserInsightCandidate(
        "Moved to a new city last spring.", learner.id, learner.text, "last spring"
    )
    result = validate_candidate(
        PracticeCandidate("Discussed a past change.", user_insights=(insight,)),
        mode="practice",
        turns=(learner,),
    )
    assert result.user_insights[0].text == insight.text
    assert result.user_insights[0].source.quote == learner.text
    assert not hasattr(result.user_insights[0], "category")
    with pytest.raises(ValueError, match="user insight"):
        validate_candidate(
            PracticeCandidate("A recap.", user_insights=(replace(insight, text="x" * 121),)),
            mode="practice",
            turns=(learner,),
        )
    with pytest.raises(ValueError, match="too many user"):
        validate_candidate(
            PracticeCandidate("A recap.", user_insights=(insight,) * 3),
            mode="practice",
            turns=(learner,),
        )


def test_prompt_prioritizes_language_without_fact_categories_or_scenarios() -> None:
    prompt = build_extraction_prompt(mode="learning", context=CONTEXT)
    assert "optional and lowest priority" in prompt
    assert "at most 120 characters" in prompt
    assert "language_items" in prompt and "capability_attempts" in prompt
    assert "Use category" not in prompt
    assert "category interest" not in prompt
    assert "For example" not in prompt
    assert CONTEXT.lesson_definition is not None
    assert CONTEXT.lesson_definition.content_version in prompt


@pytest.mark.asyncio
async def test_decisions_verification_preserves_refusals_and_drops_dangling_item_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tutor, learner, candidate = _practice()
    analysis = validate_candidate(
        candidate, mode="learning", context=CONTEXT, turns=(tutor, learner)
    )
    provider = OpenAIDecisionsReviewer("unused-test-key", probability_threshold=0.8)
    answers = [
        {"name": "language_items.1", "type": "refusal"},
        {"name": "item_practices.1", "type": "predicate", "probability": 0.95},
        {"name": "capability_attempts.1", "type": "predicate", "probability": 0.95},
    ]
    create = AsyncMock(return_value=_decision(answers))
    monkeypatch.setattr(provider._client.decisions, "create", create)
    review = await provider.review_current(
        context=CONTEXT, turns=(tutor, learner), analysis=analysis
    )
    assert review.results[0].type == "refusal"
    assert review.analysis.language_items == review.analysis.item_practices == ()
    assert review.analysis.capability_attempts == ()
    assert review.probability_threshold == 0.8
    assert len(review.input_digest) == 64
    assert "store" not in create.call_args.kwargs
    assert create.call_args.kwargs["model"] == "gpt-6-luna"


@pytest.mark.asyncio
async def test_cumulative_benchmark_preserves_oldest_evidence_and_uncertain_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tutor, learner, candidate = _practice()
    analysis = validate_candidate(
        candidate, mode="learning", context=CONTEXT, turns=(tutor, learner)
    )
    records = tuple(
        HistoricalLearningRecord(
            PROFILE_ID,
            uuid4(),
            uuid4(),
            datetime(2026, 10, 1, tzinfo=UTC) + timedelta(days=index),
            LESSONS[0].key,
            "beginner-conversation-v2",
            analysis.language_items,
            analysis.item_practices,
            analysis.capability_attempts,
        )
        for index in range(7)
    )
    history = LearningHistory(PROFILE_ID, 7, tuple(reversed(records)))
    provider = OpenAIDecisionsReviewer("unused-test-key", probability_threshold=0.8)

    async def respond(**kwargs: object) -> Decision:
        return _decision(_answers(tuple(kwargs["questions"])))  # type: ignore[arg-type]

    create = AsyncMock(side_effect=respond)
    monkeypatch.setattr(provider._client.decisions, "create", create)
    benchmark = await provider.benchmark(
        context=CONTEXT, turns=(tutor, learner), analysis=analysis, history=history
    )
    payload = json.loads(create.call_args.kwargs["input"])
    assert len(payload["complete_eligible_history"]) == 7
    assert payload["complete_eligible_history"][0]["analysis_run_id"] == str(
        records[0].analysis_run_id
    )
    assert "user_insights" not in payload["accepted_current"]
    assert benchmark.source_analysis_ids == tuple(record.analysis_run_id for record in records) + (
        ANALYSIS_ID,
    )
    assert benchmark.history_revision == 7
    assert benchmark.lesson_result.result.score == 2.4
    assert [item.probability for item in benchmark.lesson_result.result.probabilities] == [
        0,
        0.1,
        0.4,
        0.5,
    ]
    assert benchmark.rubric_version == "beginner-lesson-01-rubric-v1"
    assert benchmark.complete


@pytest.mark.asyncio
async def test_incomplete_or_other_profile_history_cannot_be_benchmarked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tutor, learner, candidate = _practice()
    analysis = validate_candidate(
        candidate, mode="learning", context=CONTEXT, turns=(tutor, learner)
    )
    provider = OpenAIDecisionsReviewer("unused-test-key", probability_threshold=0.8)
    create = AsyncMock()
    monkeypatch.setattr(provider._client.decisions, "create", create)
    for history in (
        LearningHistory(PROFILE_ID, 0, (), complete=False),
        LearningHistory(uuid4(), 0, ()),
    ):
        with pytest.raises(ValueError, match="complete owned history"):
            await provider.benchmark(
                context=CONTEXT, turns=(tutor, learner), analysis=analysis, history=history
            )
    create.assert_not_called()


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_type", "nan"])
def test_malformed_decisions_answers_fail_closed(mutation: str) -> None:
    questions: tuple[Question, ...] = (
        {"name": "verified", "type": "predicate", "instructions": "Verify"},
    )
    answers: list[dict[str, object]] = [
        {"name": "verified", "type": "predicate", "probability": 0.9}
    ]
    if mutation == "missing":
        answers = []
    elif mutation == "duplicate":
        answers *= 2
    elif mutation == "wrong_type":
        answers[0] = {
            "name": "verified",
            "type": "score",
            "score": 0,
            "confidence": 0.9,
            "probabilities": [],
        }
    else:
        answers[0]["probability"] = float("nan")
    with pytest.raises(ValueError):
        validate_decision_response(_decision(answers), questions)


def test_part_one_rubric_history_is_preserved_in_catalog() -> None:
    old = CodeCourseCatalog().course_version(
        base_language_id="english", target_language_id="mandarin", version=PART1_FRAMEWORK_ID
    )
    assert old is not None
    definition = published_lesson_definition(
        course=old, lesson_key=LESSONS[0].key, level="beginner"
    )
    assert definition is not None
    assert definition.content_version == "beginner-conversation-v1"
    assert definition.rubric is None
    assert BEGINNER_LESSON_DEFINITIONS[0].rubric is not None


@pytest.mark.asyncio
async def test_structured_extractor_emits_groundable_items_and_category_free_insights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tutor, learner, _ = _practice()
    evidence = {
        "learner_turn_id": str(learner.id),
        "learner_quote": learner.text,
        "opportunity_turn_id": str(tutor.id),
        "opportunity_quote": tutor.text,
        "assistance": "modelled",
    }
    parsed = _LearningOutput.model_validate(
        {
            "summary": "Practiced an interest.",
            "observations": [],
            "corrections": [],
            "user_insights": [],
            "language_items": [
                {
                    "key": "like",
                    "form": "我喜欢",
                    "meaning": "I like",
                    "kind": "phrase",
                    "capability_keys": ["express-detail"],
                    "known_item_id": None,
                    "introduction": {"tutor_turn_id": str(tutor.id), "tutor_quote": tutor.text},
                }
            ],
            "item_practices": [
                {
                    "item_key": "like",
                    "evidence": evidence,
                    "outcome": "communicated",
                    "opportunity_type": "production",
                }
            ],
            "capability_attempts": [
                {
                    "capability_key": "express-detail",
                    "evidence": evidence,
                    "outcome": "communicated",
                    "opportunity_type": "production",
                    "item_keys": ["like"],
                }
            ],
        }
    )
    extractor = OpenAIExtractor("unused-test-key")
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))
    monkeypatch.setattr(extractor._client.responses, "parse", parse)
    candidate = await extractor.extract(
        mode="learning", model="synthetic-model", context=CONTEXT, turns=(tutor, learner)
    )
    result = validate_candidate(candidate, mode="learning", turns=(tutor, learner), context=CONTEXT)
    assert result.language_items[0].form == "我喜欢"
    assert len(result.capability_attempts) == 1
    assert parse.call_args.kwargs["store"] is False
    with pytest.raises(ValidationError):
        _LearningOutput.model_validate(
            {
                "summary": "Recap",
                "observations": [],
                "corrections": [],
                "user_insights": [
                    {
                        "text": "x" * 121,
                        "source_turn_id": str(learner.id),
                        "source_quote": learner.text,
                        "temporal_context": None,
                    }
                ],
            }
        )
