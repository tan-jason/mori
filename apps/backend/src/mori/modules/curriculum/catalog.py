"""Supported languages using Mori's shared lesson framework."""

from __future__ import annotations

from dataclasses import dataclass

from mori.modules.curriculum.curriculum import (
    BEGINNER_LESSON_DEFINITIONS,
    FRAMEWORK_ID,
    FRAMEWORK_ITEMS,
    LEGACY_FRAMEWORK_ID,
    PART1_BEGINNER_LESSON_DEFINITIONS,
    PART1_FRAMEWORK_ID,
)
from mori.modules.curriculum.domain import (
    CoursePairView,
    LessonDefinition,
    PublishedCourse,
    validate_published_course,
)


@dataclass(frozen=True, slots=True)
class EvidenceRule:
    version: str
    evidence_kind: str
    minimum_distinct_turns: int
    confidence_threshold: float
    mastery_threshold: float
    enabled: bool
    requirement: str


TRANSCRIPT_RULE = EvidenceRule(
    version="transcript",
    evidence_kind="use",
    minimum_distinct_turns=1,
    confidence_threshold=1.0,
    mastery_threshold=1.0,
    enabled=False,
    requirement=(
        "Accept only learner speech cited to an exact finalized turn. "
        "Require a relevant response and a clear follow-up where the objective asks "
        "for one. Do not infer pronunciation mastery from transcript text."
    ),
)


EVIDENCE_RULES: dict[str, EvidenceRule] = {item.key: TRANSCRIPT_RULE for item in FRAMEWORK_ITEMS}

_TARGET_LANGUAGES = (
    ("mandarin", "Mandarin", "中文"),
    ("spanish", "Spanish", "Español"),
    ("french", "French", "Français"),
    ("portuguese", "Portuguese", "Português"),
    ("japanese", "Japanese", "日本語"),
    ("korean", "Korean", "한국어"),
    ("vietnamese", "Vietnamese", "Tiếng Việt"),
)

_BASE_LANGUAGE_ID = "english"
_TARGET_LANGUAGE_IDS = frozenset(target for target, _, _ in _TARGET_LANGUAGES)
MORI_COURSE = PublishedCourse(
    curriculum_version=FRAMEWORK_ID,
    language_policy_version="mori-language-v1",
    voice_policy_version="mori-voice-v1",
    items=FRAMEWORK_ITEMS,
    framework_version=FRAMEWORK_ID,
    lesson_definitions=BEGINNER_LESSON_DEFINITIONS,
)
PART1_MORI_COURSE = PublishedCourse(
    curriculum_version=PART1_FRAMEWORK_ID,
    language_policy_version="mori-language-v1",
    voice_policy_version="mori-voice-v1",
    items=FRAMEWORK_ITEMS,
    framework_version=PART1_FRAMEWORK_ID,
    lesson_definitions=PART1_BEGINNER_LESSON_DEFINITIONS,
)
LEGACY_MORI_COURSE = PublishedCourse(
    curriculum_version=LEGACY_FRAMEWORK_ID,
    language_policy_version="mori-language-v1",
    voice_policy_version="mori-voice-v1",
    items=FRAMEWORK_ITEMS,
    framework_version=LEGACY_FRAMEWORK_ID,
)


def published_lesson_definition(
    *,
    course: PublishedCourse,
    lesson_key: str,
    level: str,
) -> LessonDefinition | None:
    """Resolve the definition pinned by a published course, never latest content."""
    return next(
        (
            definition
            for definition in course.lesson_definitions
            if definition.lesson_key == lesson_key and definition.level == level
        ),
        None,
    )


def supported_languages(*, base_language_id: str, target_language_id: str) -> bool:
    return base_language_id == _BASE_LANGUAGE_ID and target_language_id in _TARGET_LANGUAGE_IDS


class CodeCourseCatalog:
    async def language_pairs(self) -> tuple[CoursePairView, ...]:
        return tuple(
            CoursePairView(
                base_language_id=_BASE_LANGUAGE_ID,
                target_language_id=target,
                base_language_name="English",
                target_language_name=name,
                target_native_name=native_name,
                available=True,
            )
            for target, name, native_name in _TARGET_LANGUAGES
        )

    async def is_available(self, *, base_language_id: str, target_language_id: str) -> bool:
        return supported_languages(
            base_language_id=base_language_id, target_language_id=target_language_id
        )

    async def published_course(
        self, *, base_language_id: str, target_language_id: str
    ) -> PublishedCourse | None:
        if supported_languages(
            base_language_id=base_language_id, target_language_id=target_language_id
        ):
            return MORI_COURSE
        return None

    def course_version(
        self, *, base_language_id: str, target_language_id: str, version: str
    ) -> PublishedCourse | None:
        if supported_languages(
            base_language_id=base_language_id, target_language_id=target_language_id
        ):
            return next(
                (
                    course
                    for course in (MORI_COURSE, PART1_MORI_COURSE, LEGACY_MORI_COURSE)
                    if course.curriculum_version == version
                ),
                None,
            )
        return None


validate_published_course(MORI_COURSE)
validate_published_course(PART1_MORI_COURSE)
validate_published_course(LEGACY_MORI_COURSE)
if set(EVIDENCE_RULES) != {item.key for item in FRAMEWORK_ITEMS}:
    raise ValueError("course evidence rules do not match framework lessons")
