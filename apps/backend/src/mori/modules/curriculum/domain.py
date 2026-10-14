"""Published course catalog read values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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

Assistance = Literal["independent", "cued", "modelled", "unknown"]


@dataclass(frozen=True, slots=True)
class CapabilityEvidenceRequirement:
    """Semantic evidence contract, not an enabled advancement rule."""

    outcome: Literal["communicated"]
    permitted_support: tuple[Assistance, ...]
    productive_use: bool
    varied_opportunities: bool
    later_session_recall: bool

    def __post_init__(self) -> None:
        if (
            self.outcome != "communicated"
            or not isinstance(self.permitted_support, tuple)
            or not self.permitted_support
            or len(set(self.permitted_support)) != len(self.permitted_support)
            or any(
                support not in {"independent", "cued", "modelled", "unknown"}
                for support in self.permitted_support
            )
            or any(
                type(value) is not bool
                for value in (
                    self.productive_use,
                    self.varied_opportunities,
                    self.later_session_recall,
                )
            )
        ):
            raise ValueError("invalid capability evidence requirement")


@dataclass(frozen=True, slots=True)
class LessonCapability:
    key: str
    description: str
    evidence: CapabilityEvidenceRequirement

    def __post_init__(self) -> None:
        if (
            not self.key
            or self.key != self.key.strip()
            or not self.description.strip()
            or not isinstance(self.evidence, CapabilityEvidenceRequirement)
        ):
            raise ValueError("invalid lesson capability")


@dataclass(frozen=True, slots=True)
class PerformanceLevel:
    key: str
    description: str

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.description.strip():
            raise ValueError("invalid performance level")


@dataclass(frozen=True, slots=True)
class LessonSuccessCriterion:
    key: str
    description: str
    capability_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not self.key.strip()
            or not self.description.strip()
            or not isinstance(self.capability_keys, tuple)
            or not self.capability_keys
            or len(set(self.capability_keys)) != len(self.capability_keys)
        ):
            raise ValueError("invalid lesson success criterion")


@dataclass(frozen=True, slots=True)
class LessonRubric:
    version: str
    levels: tuple[PerformanceLevel, ...]
    ready_level_key: str
    overall_instructions: str

    def __post_init__(self) -> None:
        if (
            not self.version.strip()
            or not isinstance(self.levels, tuple)
            or len(self.levels) < 2
            or any(not isinstance(level, PerformanceLevel) for level in self.levels)
            or len({level.key for level in self.levels}) != len(self.levels)
            or self.ready_level_key not in {level.key for level in self.levels}
            or not self.overall_instructions.strip()
        ):
            raise ValueError("invalid lesson rubric")


@dataclass(frozen=True, slots=True)
class LessonDefinition:
    """A published, immutable goal and ordered capability contract."""

    lesson_key: str
    content_version: str
    level: Literal["beginner", "intermediate", "advanced"]
    goal: str
    capabilities: tuple[LessonCapability, ...]
    suggested_encounters: int | None = None
    success_criteria: tuple[LessonSuccessCriterion, ...] = ()
    rubric: LessonRubric | None = None

    def __post_init__(self) -> None:
        if (
            not self.lesson_key.strip()
            or not self.content_version.strip()
            or self.level not in LEVEL_ORDER
            or not self.goal.strip()
            or not isinstance(self.capabilities, tuple)
            or not self.capabilities
            or any(not isinstance(item, LessonCapability) for item in self.capabilities)
            or len({item.key for item in self.capabilities}) != len(self.capabilities)
            or (
                self.suggested_encounters is not None
                and (type(self.suggested_encounters) is not int or self.suggested_encounters < 1)
            )
        ):
            raise ValueError("invalid lesson definition")
        if (
            not isinstance(self.success_criteria, tuple)
            or any(not isinstance(item, LessonSuccessCriterion) for item in self.success_criteria)
            or len({item.key for item in self.success_criteria}) != len(self.success_criteria)
            or any(
                key not in self.capability_keys
                for item in self.success_criteria
                for key in item.capability_keys
            )
            or bool(self.success_criteria) != (self.rubric is not None)
            or (self.rubric is not None and not isinstance(self.rubric, LessonRubric))
        ):
            raise ValueError("invalid lesson scoring contract")

    @property
    def capability_keys(self) -> tuple[str, ...]:
        return tuple(capability.key for capability in self.capabilities)


@dataclass(frozen=True, slots=True)
class NewItemAllowance:
    """Maximum deliberate teaching targets, not required introductions."""

    maximum: int = 2

    def __post_init__(self) -> None:
        if type(self.maximum) is not int or not 1 <= self.maximum <= 5:
            raise ValueError("new-item allowance must be from one to five")


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
    conversation_guidance: str | None = None


@dataclass(frozen=True, slots=True)
class PublishedCourse:
    curriculum_version: str
    language_policy_version: str
    voice_policy_version: str
    items: tuple[CurriculumItem, ...]
    framework_version: str | None = None
    lesson_definitions: tuple[LessonDefinition, ...] = ()


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
    if not course.items or not course.language_policy_version or not course.voice_policy_version:
        raise ValueError("published course is incomplete")
    if course.framework_version is None and {
        item.level for item in course.items if item.enabled and item.purpose == "diagnostic"
    } != set(LEVEL_ORDER):
        raise ValueError("published course is missing a starting diagnostic")
    by_key = {item.key: item for item in course.items}
    if len(by_key) != len(course.items):
        raise ValueError("duplicate curriculum item key")
    if not isinstance(course.lesson_definitions, tuple) or any(
        not isinstance(definition, LessonDefinition) or definition.lesson_key not in by_key
        for definition in course.lesson_definitions
    ):
        raise ValueError("lesson definition is outside the curriculum")
    if len({(item.lesson_key, item.level) for item in course.lesson_definitions}) != len(
        course.lesson_definitions
    ):
        raise ValueError("duplicate lesson definition")
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
            (
                item.level != "all"
                if course.framework_version is not None
                else item.level not in LEVEL_ORDER
            )
            or item.kind not in {"vocabulary", "grammar", "conversation", "pronunciation"}
            or item.purpose not in {"diagnostic", "skill"}
            or not (item.target_language_content or item.conversation_guidance)
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

    if course.framework_version is not None:
        by_key = {item.key: item for item in course.items}
        for keys in (context.repair_keys, context.due_keys):
            for key in sorted(keys):
                item = by_key.get(key)
                if item is not None and item.enabled:
                    return (PlannedObjective(item.label, "graded", item.key),)
        next_item = next(
            (
                item
                for item in course.items
                if item.enabled and item.key not in context.mastered_keys
            ),
            course.items[-1],
        )
        return (PlannedObjective(next_item.label, "graded", next_item.key),)

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
