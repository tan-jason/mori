"""Claims require finalized learner turns and practice never carries grades."""

import subprocess
import sys
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from mori.modules.curriculum.curriculum import FRAMEWORK_ID, LESSONS
from mori.modules.learning.domain import (
    FinalTurn,
    InsightCandidate,
    LearningCandidate,
    ObservationCandidate,
    PracticeCandidate,
    validate_candidate,
)
from mori.modules.learning.evidence import AnalysisContext, EvidenceCandidate, LessonContext
from mori.modules.learning.extractor import _ObservationOutput
from mori.modules.learning.prompt import build_extraction_prompt

LESSON = LESSONS[0]
CONTEXT = AnalysisContext(
    "english", "mandarin", FRAMEWORK_ID, LessonContext(LESSON.key, LESSON.label, LESSON.guidance)
)


def _observation(
    detail: str, turn_id: UUID, quote: str, confidence: float = 0.9
) -> ObservationCandidate:
    return ObservationCandidate(
        "use",
        detail,
        confidence,
        LESSON.key,
        (EvidenceCandidate(turn_id, quote, None, None, "unknown"),),
    )


def test_rejects_fabricated_and_tutor_turn_references() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "I live nearby")
    tutor = FinalTurn(uuid4(), 2, "tutor", "Where do you live?")
    for invalid_id in (uuid4(), tutor.id):
        candidate = LearningCandidate(
            "A short introduction.",
            (_observation("Described where they live.", invalid_id, "I live nearby"),),
            (),
        )
        with pytest.raises(ValueError, match="ungrounded"):
            validate_candidate(candidate, mode="learning", turns=(learner, tutor), context=CONTEXT)


def test_practice_output_is_summary_only() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "Hello")
    candidate = PracticeCandidate("A brief conversation.")
    accepted = validate_candidate(candidate, mode="practice", turns=(learner,))
    assert accepted.observations == accepted.corrections == ()
    with pytest.raises(ValueError, match="practice analysis"):
        validate_candidate(
            LearningCandidate("A brief conversation.", (), ()),
            mode="practice",
            turns=(learner,),
        )


def test_uncertain_observation_is_omitted_without_losing_recap() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "I live nearby")
    candidate = LearningCandidate(
        "A short introduction.",
        (_observation("Described where they live.", learner.id, "I live nearby", 0.3),),
        (),
    )
    accepted = validate_candidate(candidate, mode="learning", turns=(learner,), context=CONTEXT)
    assert accepted.summary == "A short introduction."
    assert accepted.observations == ()


def test_only_explicit_bounded_interests_become_insights() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "I like cooking and trying recipes.")
    accepted = validate_candidate(
        PracticeCandidate(
            "We talked about food.",
            (InsightCandidate("cooking", learner.id, "I like cooking", "interest", 0.9),),
        ),
        mode="practice",
        turns=(learner,),
    )
    assert len(accepted.insights) == 1
    assert accepted.insights[0].fact == "Enjoys cooking."

    for candidate in (
        InsightCandidate("diabetes", learner.id, "I like cooking", "interest", 0.9),
        InsightCandidate("cooking", learner.id, "I have diabetes", "interest", 0.9),
        InsightCandidate("cooking", uuid4(), "I like cooking", "interest", 0.9),
    ):
        filtered = validate_candidate(
            PracticeCandidate("We talked about food.", (candidate,)),
            mode="practice",
            turns=(learner,),
        )
        assert filtered.insights == ()


def test_specific_insights_can_share_a_turn_and_include_occupation() -> None:
    learner = FinalTurn(
        uuid4(),
        1,
        "learner",
        "I like hiking and playing beach volleyball. I work as a software engineer.",
    )
    accepted = validate_candidate(
        PracticeCandidate(
            "The learner shared activities and work.",
            (
                InsightCandidate("hiking", learner.id, "I like hiking", "interest", 0.95),
                InsightCandidate(
                    "playing beach volleyball",
                    learner.id,
                    "I like hiking and playing beach volleyball",
                    "interest",
                    0.95,
                ),
                InsightCandidate(
                    "a software engineer",
                    learner.id,
                    "I work as a software engineer",
                    "occupation",
                    0.95,
                ),
            ),
        ),
        mode="practice",
        turns=(learner,),
    )
    assert [item.fact for item in accepted.insights] == [
        "Enjoys hiking.",
        "Enjoys playing beach volleyball.",
        "Works as a software engineer.",
    ]


def test_learning_requires_grounded_language_progress_not_meta_requests() -> None:
    learner = FinalTurn(uuid4(), 1, "learner", "我下班后通常打沙滩排球。")
    accepted = validate_candidate(
        LearningCandidate(
            "Practiced talking about after-work routines.",
            (
                _observation(
                    "Combined 下班后 and 通常 to describe a regular after-work activity.",
                    learner.id,
                    "我下班后通常打沙滩排球。",
                ),
            ),
            (),
        ),
        mode="learning",
        turns=(learner,),
        context=CONTEXT,
    )
    assert len(accepted.observations) == 1
    filtered = validate_candidate(
        LearningCandidate(
            "A recap.",
            (
                _observation(
                    "Requested another role-play.",
                    learner.id,
                    "我下班后通常打沙滩排球。",
                ),
            ),
            (),
        ),
        mode="learning",
        turns=(learner,),
        context=CONTEXT,
    )
    assert filtered.observations == ()


def test_standalone_analysis_worker_resolves_foreign_keys() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from mori.modules.learning.application import AnalysisService; "
            "from mori.persistence.base import Base; "
            "AnalysisService(session_maker=None, extractor=None, fact_digest_key='test'); "
            "[fk.column for table in Base.metadata.tables.values() for fk in table.foreign_keys]",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_extractor_schema_restricts_observation_categories() -> None:
    with pytest.raises(ValidationError):
        _ObservationOutput.model_validate(
            {
                "kind": "language_practice",
                "detail": "Practiced a sentence.",
                "learner_turn_ids": [str(uuid4())],
                "confidence": 0.9,
            }
        )


def test_capture_prompt_separates_learning_from_practice() -> None:
    lesson = "Introduce yourself and share a few details about your life."
    learning = build_extraction_prompt(mode="learning", context=CONTEXT)
    practice = build_extraction_prompt(mode="practice", context=replace(CONTEXT, lesson=None))
    assert lesson in learning
    assert "bundled learnings" in learning
    assert "bundled learnings" not in practice
    assert "specific personal insights" in learning
    assert "specific personal insights" in practice
    with pytest.raises(ValueError, match="unsupported analysis mode"):
        build_extraction_prompt(mode="other", context=CONTEXT)
