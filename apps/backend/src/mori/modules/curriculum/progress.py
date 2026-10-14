"""Profile-owned committed evidence interpreted without model or database calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from uuid import UUID

from mori.modules.curriculum.domain import Assistance, LessonDefinition


@dataclass(frozen=True, slots=True)
class PracticeOccurrence:
    id: UUID
    session_id: UUID
    occurred_at: datetime
    lesson_key: str
    capability_key: str
    item_id: UUID | None
    assistance: Assistance
    communicated: bool


@dataclass(frozen=True, slots=True)
class RecallItem:
    id: UUID
    profile_id: UUID
    form: str
    meaning: str
    kind: str
    capability_keys: tuple[str, ...]
    introduced_session_id: UUID
    introduced_at: datetime
    eligible: bool = True


@dataclass(frozen=True, slots=True)
class CriterionDistribution:
    key: str
    assessable: bool
    probabilities: tuple[float, ...]

    def __post_init__(self) -> None:
        if (
            not self.key
            or not self.probabilities
            or any(not isfinite(p) or not 0 <= p <= 1 for p in self.probabilities)
            or abs(sum(self.probabilities) - 1) > 0.001
        ):
            raise ValueError("invalid criterion distribution")


@dataclass(frozen=True, slots=True)
class LessonBenchmark:
    lesson_key: str
    content_version: str
    rubric_version: str
    history_revision: int
    criteria: tuple[CriterionDistribution, ...]
    lesson: CriterionDistribution
    complete: bool = True


@dataclass(frozen=True, slots=True)
class ProfileProgress:
    profile_id: UUID
    history_revision: int = 0
    practices: tuple[PracticeOccurrence, ...] = ()
    items: tuple[RecallItem, ...] = ()
    benchmarks: tuple[LessonBenchmark, ...] = ()
    active_lesson_key: str | None = None

    def __post_init__(self) -> None:
        if self.history_revision < 0 or any(i.profile_id != self.profile_id for i in self.items):
            raise ValueError("progress belongs to one language profile")
        if len({p.id for p in self.practices}) != len(self.practices):
            raise ValueError("duplicate committed practice")
        if len({i.id for i in self.items}) != len(self.items):
            raise ValueError("duplicate language item")


def usable_encounters(progress: ProfileProgress, lesson_key: str) -> int:
    return len({p.session_id for p in progress.practices if p.lesson_key == lesson_key})


def recurring_help(
    progress: ProfileProgress,
) -> tuple[frozenset[UUID], frozenset[tuple[str, str]]]:
    """Two distinct later difficulties activate help; independent reuse clears it."""
    items = {i.id: i for i in progress.items}
    item_help: set[UUID] = set()
    capability_help: set[tuple[str, str]] = set()
    targets: dict[tuple[str, str, str], list[PracticeOccurrence]] = {}
    for practice in progress.practices:
        targets.setdefault(("capability", practice.lesson_key, practice.capability_key), []).append(
            practice
        )
        if practice.item_id in items:
            targets.setdefault(("item", "", str(practice.item_id)), []).append(practice)
    for (kind, lesson_key, key), practices in targets.items():
        by_session: dict[UUID, list[PracticeOccurrence]] = {}
        for practice in sorted(
            practices, key=lambda p: (p.occurred_at, str(p.session_id), str(p.id))
        ):
            by_session.setdefault(practice.session_id, []).append(practice)
        first_session = (
            items[UUID(key)].introduced_session_id if kind == "item" else next(iter(by_session))
        )
        later_help: set[UUID] = set()
        for session_id, attempts in by_session.items():
            if session_id == first_session:
                continue
            if any(p.communicated and p.assistance == "independent" for p in attempts):
                later_help.clear()
            elif any(p.assistance in {"cued", "modelled"} for p in attempts):
                later_help.add(session_id)
        if len(later_help) >= 2:
            if kind == "item":
                item_help.add(UUID(key))
            else:
                capability_help.add((lesson_key, key))
    return frozenset(item_help), frozenset(capability_help)


def current_benchmark(
    progress: ProfileProgress, definition: LessonDefinition
) -> LessonBenchmark | None:
    if definition.rubric is None:
        return None
    return next(
        (
            benchmark
            for benchmark in reversed(progress.benchmarks)
            if benchmark.lesson_key == definition.lesson_key
            and benchmark.content_version == definition.content_version
            and benchmark.rubric_version == definition.rubric.version
            and benchmark.history_revision == progress.history_revision
            and benchmark.complete
        ),
        None,
    )


def lesson_ready(
    progress: ProfileProgress, definition: LessonDefinition, probability_threshold: float | None
) -> bool:
    if probability_threshold is None:
        return False
    if not isfinite(probability_threshold) or not 0 < probability_threshold <= 1:
        raise ValueError("invalid advancement probability threshold")
    if definition.rubric is None:
        return False
    benchmark = current_benchmark(progress, definition)
    if benchmark is None:
        return False
    ready_index = next(
        index
        for index, level in enumerate(definition.rubric.levels)
        if level.key == definition.rubric.ready_level_key
    )
    distributions = {c.key: c for c in benchmark.criteria}
    expected = {criterion.key for criterion in definition.success_criteria}
    if set(distributions) != expected or len(distributions) != len(benchmark.criteria):
        return False
    return all(
        score.assessable
        and len(score.probabilities) == len(definition.rubric.levels)
        and sum(score.probabilities[ready_index:]) >= probability_threshold
        for score in (*distributions.values(), benchmark.lesson)
    )
