"""Versioned course definitions shipped with the application.

Changing published content requires a new curriculum or policy version. Existing
session plans retain their selected objective text and the versions used to make it.
"""

from __future__ import annotations

from dataclasses import dataclass

from mori.modules.curriculum.domain import (
    CoursePairView,
    CurriculumItem,
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
    version="transcript-v1",
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


def _item(
    key: str,
    label: str,
    level: str,
    purpose: str,
    weight: int,
    topics: tuple[str, ...],
    words: tuple[str, ...],
    content: str,
    prerequisites: tuple[str, ...] = (),
) -> CurriculumItem:
    return CurriculumItem(
        key=key,
        label=label,
        level=level,
        kind="conversation",
        purpose=purpose,
        selection_weight=weight,
        target_language_content=content,
        enabled=True,
        topic_tags=topics,
        word_tags=words,
        prerequisites=prerequisites,
    )


MANDARIN_FOUNDATIONS_V1 = PublishedCourse(
    curriculum_version="mandarin-foundations-v1",
    pair_policy_version="en-zh-pair-v1",
    voice_policy_version="mandarin-voice-v1",
    pair_policy=(
        "Use Standard Mandarin for examples and spoken practice. "
        "Give brief English rescue scaffolds when understanding breaks down. "
        "Give Mandarin-specific pronunciation guidance only when the signal is clear; "
        "model one repair and invite a retry."
    ),
    voice_policy=(
        "Target spoken language: Standard Mandarin. Base language for brief "
        "explanations: English. Playback pace follows learner preference "
        "independently of accent."
    ),
    items=(
        _item(
            "beginner-check-in",
            "Share a simple introduction and answer a follow-up.",
            "beginner",
            "diagnostic",
            1,
            ("introduction",),
            (),
            "你好，我叫……。你呢？",
        ),
        _item(
            "greetings",
            "Greet someone and introduce yourself in Mandarin.",
            "beginner",
            "skill",
            2,
            ("introduction", "people"),
            ("hello", "name"),
            "你好。我叫……。很高兴认识你。",
            ("beginner-check-in",),
        ),
        _item(
            "daily-routine",
            "Describe one part of your day in Mandarin.",
            "beginner",
            "skill",
            3,
            ("daily life", "weekend"),
            ("today", "morning"),
            "今天早上我……。",
            ("greetings",),
        ),
        _item(
            "intermediate-check-in",
            "Describe a recent event and answer a follow-up.",
            "intermediate",
            "diagnostic",
            1,
            ("weekend", "travel"),
            (),
            "上周末我去了……，然后……。",
        ),
        _item(
            "past-event",
            "Tell a short story about a recent event.",
            "intermediate",
            "skill",
            2,
            ("weekend", "travel"),
            ("yesterday", "market"),
            "昨天我去了市场，买了……。",
            ("intermediate-check-in",),
        ),
        _item(
            "advanced-check-in",
            "Explain an opinion and respond to a different view.",
            "advanced",
            "diagnostic",
            1,
            ("opinions",),
            (),
            "我认为……，因为……。你怎么看？",
        ),
        _item(
            "reasoned-opinion",
            "Support an opinion with a reason and an example.",
            "advanced",
            "skill",
            2,
            ("opinions", "work"),
            ("because", "however"),
            "我认为……，因为……。不过，也可以说……。",
            ("advanced-check-in",),
        ),
    ),
)

MANDARIN_FOUNDATIONS_V1_EVIDENCE_RULES: dict[str, EvidenceRule] = {
    item.key: TRANSCRIPT_RULE for item in MANDARIN_FOUNDATIONS_V1.items
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

_VERSIONS: dict[tuple[str, str, str], PublishedCourse] = {
    ("english", "mandarin", "mandarin-foundations-v1"): MANDARIN_FOUNDATIONS_V1,
}
_ACTIVE_VERSIONS: dict[tuple[str, str], str] = {
    ("english", "mandarin"): "mandarin-foundations-v1",
}


class CodeCourseCatalog:
    async def language_pairs(self) -> tuple[CoursePairView, ...]:
        return tuple(
            CoursePairView(
                base_language_id="english",
                target_language_id=target,
                base_language_name="English",
                target_language_name=name,
                target_native_name=native_name,
                available=("english", target) in _ACTIVE_VERSIONS,
            )
            for target, name, native_name in _PAIR_NAMES
        )

    async def is_available(self, *, base_language_id: str, target_language_id: str) -> bool:
        return (base_language_id, target_language_id) in _ACTIVE_VERSIONS

    async def published_course(
        self, *, base_language_id: str, target_language_id: str
    ) -> PublishedCourse | None:
        version = _ACTIVE_VERSIONS.get((base_language_id, target_language_id))
        if version is None:
            return None
        return self.course_version(
            base_language_id=base_language_id,
            target_language_id=target_language_id,
            version=version,
        )

    def course_version(
        self, *, base_language_id: str, target_language_id: str, version: str
    ) -> PublishedCourse | None:
        return _VERSIONS.get((base_language_id, target_language_id, version))


for _key, _course in _VERSIONS.items():
    if _key[2] != _course.curriculum_version:
        raise ValueError("course registry version does not match its definition")
    validate_published_course(_course)
    if _course is MANDARIN_FOUNDATIONS_V1 and set(MANDARIN_FOUNDATIONS_V1_EVIDENCE_RULES) != {
        item.key for item in _course.items
    }:
        raise ValueError("course evidence rules do not match curriculum items")
for _pair, _version in _ACTIVE_VERSIONS.items():
    if (*_pair, _version) not in _VERSIONS:
        raise ValueError("active course version is missing from the registry")
