"""Published course catalog read values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CoursePairView:
    base_language_id: str
    target_language_id: str
    base_language_name: str
    target_language_name: str
    target_native_name: str
    available: bool


LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}
SELECTION_RULE_VERSION = "selector-v1"


@dataclass(frozen=True, slots=True)
class CurriculumItem:
    key: str
    label: str
    level: str
    kind: str
    purpose: str
    selection_weight: int
    target_language_content: str
    enabled: bool
    topic_tags: tuple[str, ...]
    word_tags: tuple[str, ...]
    prerequisites: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PublishedCourse:
    curriculum_version: str
    pair_policy_version: str
    voice_policy_version: str
    pair_policy: str
    voice_policy: str
    items: tuple[CurriculumItem, ...]


@dataclass(frozen=True, slots=True)
class PlanningContext:
    mode: str
    provisional_level: str | None
    topic: str | None
    requested_words: tuple[str, ...]
    mastered_keys: frozenset[str] = frozenset()
    due_keys: frozenset[str] = frozenset()
    repair_keys: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class PlannedObjective:
    label: str
    kind: str
    curriculum_item_key: str | None


def validate_published_course(course: PublishedCourse) -> None:
    """Reject incomplete, cross-version, or cyclic publication data."""
    if (
        not course.items
        or not course.pair_policy_version
        or not course.voice_policy_version
        or not course.pair_policy
        or not course.voice_policy
    ):
        raise ValueError("published course is incomplete")
    if {
        item.level for item in course.items if item.enabled and item.purpose == "diagnostic"
    } != set(LEVEL_ORDER):
        raise ValueError("published course is missing a starting diagnostic")
    by_key = {item.key: item for item in course.items}
    if len(by_key) != len(course.items):
        raise ValueError("duplicate curriculum item key")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError("curriculum contains a cycle")
        if key in visited:
            return
        visiting.add(key)
        item = by_key[key]
        if (
            item.level not in LEVEL_ORDER
            or item.kind not in {"vocabulary", "grammar", "conversation", "pronunciation"}
            or item.purpose not in {"diagnostic", "skill"}
            or not item.target_language_content
            or item.selection_weight <= 0
        ):
            raise ValueError("invalid curriculum item")
        for prerequisite in item.prerequisites:
            if prerequisite not in by_key:
                raise ValueError("prerequisite is outside the curriculum")
            visit(prerequisite)
        visiting.remove(key)
        visited.add(key)

    for key in by_key:
        visit(key)


def build_session_plan(
    context: PlanningContext, course: PublishedCourse
) -> tuple[PlannedObjective, ...]:
    validate_published_course(course)
    if context.mode == "practice":
        focus = (
            f"Have a natural conversation about {context.topic}."
            if context.topic
            else "Have a natural conversation in the target language."
        )
        return (PlannedObjective(label=focus, kind="conversation_focus", curriculum_item_key=None),)
    if context.mode != "learning" or context.provisional_level not in LEVEL_ORDER:
        raise ValueError("invalid learning placement")

    level = context.provisional_level
    eligible = [
        item
        for item in course.items
        if item.enabled
        and LEVEL_ORDER[item.level] <= LEVEL_ORDER[level]
        and all(prerequisite in context.mastered_keys for prerequisite in item.prerequisites)
        and (
            item.key not in context.mastered_keys
            or item.key in context.due_keys
            or item.key in context.repair_keys
        )
        and (item.purpose == "skill" or item.level == level)
    ]
    if not eligible:
        eligible = [
            item
            for item in course.items
            if item.enabled
            and LEVEL_ORDER[item.level] <= LEVEL_ORDER[level]
            and all(prerequisite in context.mastered_keys for prerequisite in item.prerequisites)
        ]
        if not eligible:
            raise ValueError("no eligible curriculum objective")

    # Until a diagnostic is demonstrated, use a single placement objective.
    diagnostic = min(
        (item for item in eligible if item.purpose == "diagnostic" and item.level == level),
        key=lambda item: (item.selection_weight, item.key),
        default=None,
    )
    if (
        diagnostic is not None
        and not context.mastered_keys
        and not context.due_keys
        and not context.repair_keys
    ):
        return (PlannedObjective(diagnostic.label, "graded", diagnostic.key),)

    topic = context.topic.casefold() if context.topic else ""
    words = {word.casefold() for word in context.requested_words}
    eligible.sort(
        key=lambda item: (
            0 if item.key in context.repair_keys else 1,
            0 if item.key in context.due_keys else 1,
            0 if words.intersection(item.word_tags) else 1,
            0 if topic and any(tag in topic for tag in item.topic_tags) else 1,
            abs(LEVEL_ORDER[item.level] - LEVEL_ORDER[level]),
            item.selection_weight,
            item.key,
        )
    )
    return tuple(PlannedObjective(item.label, "graded", item.key) for item in eligible[:3])
