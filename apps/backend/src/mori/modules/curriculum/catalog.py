"""Language-pair configuration composed with Mori's shared lesson framework."""

from __future__ import annotations

from dataclasses import dataclass

from mori.modules.curriculum.curriculum import FRAMEWORK_ID, FRAMEWORK_ITEMS
from mori.modules.curriculum.domain import (
    CoursePairView,
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


# The lessons are Mori's shared course. This publication adds the currently
# supported language pair's speaking and voice rules.
MANDARIN_COURSE = PublishedCourse(
    base_language_id="english",
    target_language_id="mandarin",
    curriculum_version=FRAMEWORK_ID,
    pair_policy_version="en-zh",
    voice_policy_version="mandarin-voice",
    pair_policy=(
        "Use Standard Mandarin for spoken examples. Give Mandarin-specific "
        "pronunciation guidance only when the audio clearly supports it."
    ),
    voice_policy=(
        "Target spoken language: Standard Mandarin. Base language for explanations: "
        "English. Playback pace follows learner preference independently of accent."
    ),
    items=FRAMEWORK_ITEMS,
    framework_version=FRAMEWORK_ID,
)

EVIDENCE_RULES: dict[str, EvidenceRule] = {
    item.key: TRANSCRIPT_RULE for item in FRAMEWORK_ITEMS
}

_PAIR_NAMES = (
    ("mandarin", "Mandarin", "中文"),
    ("spanish", "Spanish", "Español"),
    ("french", "French", "Français"),
    ("portuguese", "Portuguese", "Português"),
    ("japanese", "Japanese", "日本語"),
    ("korean", "Korean", "한국어"),
    ("vietnamese", "Vietnamese", "Tiếng Việt"),
)

_COURSES = {(MANDARIN_COURSE.base_language_id, MANDARIN_COURSE.target_language_id): MANDARIN_COURSE}


class CodeCourseCatalog:
    async def language_pairs(self) -> tuple[CoursePairView, ...]:
        return tuple(
            CoursePairView(
                base_language_id="english",
                target_language_id=target,
                base_language_name="English",
                target_language_name=name,
                target_native_name=native_name,
                available=("english", target) in _COURSES,
            )
            for target, name, native_name in _PAIR_NAMES
        )

    async def is_available(self, *, base_language_id: str, target_language_id: str) -> bool:
        return (base_language_id, target_language_id) in _COURSES

    async def published_course(
        self, *, base_language_id: str, target_language_id: str
    ) -> PublishedCourse | None:
        return _COURSES.get((base_language_id, target_language_id))

    def course_version(
        self, *, base_language_id: str, target_language_id: str, version: str
    ) -> PublishedCourse | None:
        course = _COURSES.get((base_language_id, target_language_id))
        return course if course is not None and course.curriculum_version == version else None


validate_published_course(MANDARIN_COURSE)
if set(EVIDENCE_RULES) != {item.key for item in FRAMEWORK_ITEMS}:
    raise ValueError("course evidence rules do not match framework lessons")
