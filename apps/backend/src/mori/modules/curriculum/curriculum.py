"""Mori's language-independent ten-lesson conversation framework."""

from __future__ import annotations

from dataclasses import dataclass, replace

from mori.modules.curriculum.domain import (
    CapabilityEvidenceRequirement,
    CurriculumItem,
    LessonCapability,
    LessonDefinition,
    LessonRubric,
    LessonSuccessCriterion,
    PerformanceLevel,
)

LEGACY_FRAMEWORK_ID = "mori-framework"
PART1_FRAMEWORK_ID = "mori-framework-v2"
FRAMEWORK_ID = "mori-framework-v3"


@dataclass(frozen=True, slots=True)
class Lesson:
    number: int
    key: str
    label: str
    guidance: str


LESSONS = (
    Lesson(
        1,
        "lesson-01-introduction",
        "Introduce yourself and share a few details about your life.",
        "Guide the learner toward using basic vocabulary and phrases to have a "
        "conversation about something familiar to them, and easy to converse about. "
        "Start with a greeting, lesson goal and a little bit about themself to get "
        "comfortable. These are possible directions, "
        "not required disclosures or a sequence of questions. When useful, help "
        "them say that they are learning the target language or ask what something "
        "means in the target language. Reuse details they share and help them "
        "combine familiar phrases with new details into a fuller account of their life.",
    ),
    Lesson(
        2,
        "lesson-02-personal-life",
        "Expand a personal introduction through connected details.",
        "Build on the learner's introduction with details they choose about their "
        "home, work or study, interests, and important people. Follow their answers "
        "and help them connect ideas into a fuller account of their life.",
    ),
    Lesson(
        3,
        "lesson-03-routines",
        "Talk about an everyday routine.",
        "Use a routine the learner chooses. Help them describe what they usually do "
        "and when, following naturally into one or two connected details.",
    ),
    Lesson(
        4,
        "lesson-04-routine-followups",
        "Compare routines and describe changes.",
        "Build on a familiar routine. Invite the learner to compare days, explain a "
        "preference, or describe what changes when plans shift.",
    ),
    Lesson(
        5,
        "lesson-05-unexpected-followups",
        "Handle an unexpected follow-up.",
        "Discuss a familiar subject, then introduce a relevant follow-up the learner "
        "could not fully predict. Give them time to clarify, think, and respond in "
        "their own way. Help them extend or redirect the answer.",
    ),
    Lesson(
        6,
        "lesson-06-real-world-exchange",
        "Navigate a real-world exchange.",
        "Invite the learner to choose a practical exchange. Food is a useful default; "
        "shopping, a cinema, a relative, or another setting are equally valid. "
        "Play the other person and let the learner pursue a real purpose.",
    ),
    Lesson(
        7,
        "lesson-07-exchange-followups",
        "Adapt during a real-world exchange.",
        "Continue or choose another practical exchange. Introduce a natural change "
        "such as a choice, clarification, unavailable option, or new request, then "
        "help the learner adapt while keeping the exchange realistic.",
    ),
    Lesson(
        8,
        "lesson-08-repair-understanding",
        "Recover when you do not understand.",
        "Create natural opportunities to ask for repetition, slower speech, a "
        "meaning, or a different explanation. Respond helpfully to the learner's "
        "repair request and return to the conversation.",
    ),
    Lesson(
        9,
        "lesson-09-events-and-plans",
        "Describe a recent event or an upcoming plan.",
        "Let the learner choose a recent event or upcoming plan. Help them tell what "
        "happened or will happen, add a relevant detail, and answer a natural follow-up.",
    ),
    Lesson(
        10,
        "lesson-10-mixed-conversation",
        "Sustain a mixed guided conversation for seven minutes.",
        "Sustain about seven minutes of connected conversation that naturally moves "
        "among familiar life topics, routines, plans, and practical exchanges. "
        "Guide transitions and support repair when needed without following a fixed script.",
    ),
)

if tuple(lesson.number for lesson in LESSONS) != tuple(range(1, 11)):
    raise ValueError("framework lessons must be numbered from one to ten")
if len({lesson.key for lesson in LESSONS}) != len(LESSONS):
    raise ValueError("framework lesson keys must be unique")

FRAMEWORK_ITEMS = tuple(
    CurriculumItem(
        key=lesson.key,
        label=lesson.label,
        level="all",
        kind="conversation",
        purpose="skill",
        selection_weight=lesson.number,
        target_language_content="",
        enabled=True,
        topic_tags=(),
        word_tags=(),
        prerequisites=(LESSONS[lesson.number - 2].key,) if lesson.number > 1 else (),
        conversation_guidance=lesson.guidance,
    )
    for lesson in LESSONS
)

# These contracts describe the evidence to collect. Advancement remains disabled
# until a versioned reducer and its qualifying thresholds are implemented.
_PRODUCTIVE_EVIDENCE = CapabilityEvidenceRequirement(
    outcome="communicated",
    permitted_support=("independent",),
    productive_use=True,
    varied_opportunities=True,
    later_session_recall=True,
)
_RESPONSE_EVIDENCE = CapabilityEvidenceRequirement(
    outcome="communicated",
    permitted_support=("independent",),
    productive_use=False,
    varied_opportunities=True,
    later_session_recall=True,
)

PART1_BEGINNER_LESSON_DEFINITIONS = (
    LessonDefinition(
        lesson_key=LESSONS[0].key,
        content_version="beginner-conversation-v1",
        level="beginner",
        goal=(
            "Share a familiar detail, answer a related question, and contribute a "
            "question or reaction that returns the turn."
        ),
        capabilities=(
            LessonCapability(
                "express-detail",
                "Express one meaningful detail using reusable language.",
                _PRODUCTIVE_EVIDENCE,
            ),
            LessonCapability(
                "answer-related-question",
                "Understand and answer a related question.",
                _RESPONSE_EVIDENCE,
            ),
            LessonCapability(
                "return-turn",
                "Contribute a reciprocal question or reaction that returns the turn.",
                _PRODUCTIVE_EVIDENCE,
            ),
        ),
        suggested_encounters=4,
    ),
    LessonDefinition(
        lesson_key=LESSONS[1].key,
        content_version="beginner-conversation-v1",
        level="beginner",
        goal=(
            "Connect details about a familiar subject and help develop the thread "
            "through a relevant follow-up."
        ),
        capabilities=(
            LessonCapability(
                "add-connected-detail",
                "Reuse familiar language to add a connected detail.",
                _PRODUCTIVE_EVIDENCE,
            ),
            LessonCapability(
                "connect-ideas",
                "Connect ideas into a meaningful contribution.",
                _PRODUCTIVE_EVIDENCE,
            ),
            LessonCapability(
                "respond-to-follow-up",
                "Respond to a fresh, relevant follow-up.",
                _RESPONSE_EVIDENCE,
            ),
            LessonCapability(
                "develop-thread",
                "Ask a relevant follow-up or volunteer another contribution.",
                _PRODUCTIVE_EVIDENCE,
            ),
        ),
    ),
)

_LESSON_ONE_RUBRIC = LessonRubric(
    version="beginner-lesson-01-rubric-v1",
    levels=(
        PerformanceLevel(
            "beginning",
            "Assessable practice does not yet communicate the required familiar detail, "
            "related response, or reciprocal contribution.",
        ),
        PerformanceLevel(
            "supported",
            "The required contribution communicates meaning with useful cues or a supplied model.",
        ),
        PerformanceLevel(
            "achieving",
            "The required contribution communicates meaning independently in a two-way exchange.",
        ),
        PerformanceLevel(
            "retaining",
            "The required contribution is recalled independently in later sessions and "
            "reused in meaningfully varied two-way exchanges.",
        ),
    ),
    ready_level_key="retaining",
    overall_instructions=(
        "Benchmark expressing a familiar detail, answering a related question, and returning "
        "the turn together. All three criteria matter; a strong detail alone does not establish "
        "a two-way conversation. Apply the ordered levels to each criterion separately, "
        "and require all criteria for the corresponding overall level."
    ),
)
_LESSON_TWO_RUBRIC = LessonRubric(
    version="beginner-lesson-02-rubric-v1",
    levels=(
        PerformanceLevel(
            "beginning",
            "Assessable contributions do not yet communicate the required connected detail, "
            "connection, follow-up response, or initiative.",
        ),
        PerformanceLevel(
            "supported",
            "The required contribution develops a connected thread with useful cues or a model.",
        ),
        PerformanceLevel(
            "achieving",
            "The required contribution independently develops a connected familiar conversation.",
        ),
        PerformanceLevel(
            "retaining",
            "Connected conversation is retained through independent later-session recall "
            "and developed in meaningfully varied fresh exchanges.",
        ),
    ),
    ready_level_key="retaining",
    overall_instructions=(
        "Benchmark adding a connected detail, connecting ideas, answering a fresh follow-up, "
        "and developing the thread through learner initiative. All four criteria matter. "
        "Apply levels to each criterion separately, and require all criteria for the "
        "corresponding overall level. Earlier lesson-one evidence can show retention but "
        "does not substitute for the connected conversation required here."
    ),
)
BEGINNER_LESSON_DEFINITIONS = tuple(
    replace(
        definition,
        content_version="beginner-conversation-v2",
        success_criteria=tuple(
            LessonSuccessCriterion(
                key=capability.key,
                description=capability.description,
                capability_keys=(capability.key,),
            )
            for capability in definition.capabilities
        ),
        rubric=rubric,
    )
    for definition, rubric in zip(
        PART1_BEGINNER_LESSON_DEFINITIONS,
        (_LESSON_ONE_RUBRIC, _LESSON_TWO_RUBRIC),
        strict=True,
    )
)
