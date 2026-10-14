"""Deterministic lesson focus, recall selection, and saved teaching allowances."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from mori.modules.curriculum.domain import Assistance, LessonDefinition, NewItemAllowance
from mori.modules.curriculum.progress import (
    ProfileProgress,
    current_benchmark,
    lesson_ready,
    recurring_help,
)

PLANNING_POLICY_VERSION = "lesson-cycle-v1"
MAX_RECALL_ITEMS = 3


@dataclass(frozen=True, slots=True)
class PlannedRecall:
    item_id: UUID
    form: str
    meaning: str
    kind: str
    capability_keys: tuple[str, ...]
    assistance: Assistance


@dataclass(frozen=True, slots=True)
class SessionLearningPlan:
    profile_id: UUID
    source_history_revision: int
    policy_version: str
    lesson_key: str
    content_version: str
    rubric_version: str
    focus_capability_key: str
    recalls: tuple[PlannedRecall, ...]
    new_item_allowance: NewItemAllowance


def plan_learning_session(
    progress: ProfileProgress,
    definitions: tuple[LessonDefinition, ...],
    *,
    probability_threshold: float | None = None,
) -> SessionLearningPlan:
    if not definitions:
        raise ValueError("no published lesson definitions")
    start = next(
        (i for i, d in enumerate(definitions) if d.lesson_key == progress.active_lesson_key), 0
    )
    selected = definitions[start]
    for index in range(start, len(definitions) - 1):
        definition = definitions[index]
        if not lesson_ready(progress, definition, probability_threshold):
            break
        selected = definitions[index + 1]
    item_help, capability_help = recurring_help(progress)
    benchmark = current_benchmark(progress, selected)
    criterion_scores = {score.key: score for score in benchmark.criteria} if benchmark else {}
    practice_counts = {
        key: len(
            {
                p.session_id
                for p in progress.practices
                if p.lesson_key == selected.lesson_key and p.capability_key == key
            }
        )
        for key in selected.capability_keys
    }

    def focus_priority(key: str) -> tuple[bool, float, int, int]:
        score = criterion_scores.get(key)
        mean = (
            sum(i * p for i, p in enumerate(score.probabilities))
            if score is not None and score.assessable
            else -1.0
        )
        return (
            (selected.lesson_key, key) not in capability_help,
            mean,
            practice_counts[key],
            selected.capability_keys.index(key),
        )

    focus = min(selected.capability_keys, key=focus_priority)
    eligible = [item for item in progress.items if item.eligible]
    last_use = {item.id: item.introduced_at for item in eligible}
    last_support: dict[UUID, Assistance] = {}
    for practice in sorted(progress.practices, key=lambda p: (p.occurred_at, str(p.id))):
        if practice.item_id in last_use:
            assert practice.item_id is not None
            last_use[practice.item_id] = max(last_use[practice.item_id], practice.occurred_at)
            last_support[practice.item_id] = practice.assistance
    chosen = []
    if eligible:
        # Recent material and older material both survive recurring-help priority.
        recent = max(eligible, key=lambda i: (last_use[i.id], str(i.id)))
        chosen.append(recent)
        older = [item for item in eligible if item.id != recent.id]
        if older:
            chosen.append(min(older, key=lambda i: (last_use[i.id], str(i.id))))
        remaining = sorted(
            (item for item in eligible if item not in chosen),
            key=lambda i: (
                i.id not in item_help,
                focus not in i.capability_keys,
                last_use[i.id],
                str(i.id),
            ),
        )
        chosen.extend(remaining[: MAX_RECALL_ITEMS - len(chosen)])
    allowance = 2
    if item_help or capability_help:
        allowance = 1
    elif progress.practices:
        latest = max(
            progress.practices, key=lambda p: (p.occurred_at, str(p.session_id))
        ).session_id
        attempts = [p for p in progress.practices if p.session_id == latest]
        if attempts and all(p.communicated and p.assistance == "independent" for p in attempts):
            comfortable_sessions = len(
                {
                    p.session_id
                    for p in progress.practices
                    if p.communicated and p.assistance == "independent"
                }
            )
            allowance = min(5, 2 + comfortable_sessions)
    if selected.rubric is None:
        raise ValueError("lesson has no published benchmark rubric")
    return SessionLearningPlan(
        profile_id=progress.profile_id,
        source_history_revision=progress.history_revision,
        policy_version=PLANNING_POLICY_VERSION,
        lesson_key=selected.lesson_key,
        content_version=selected.content_version,
        rubric_version=selected.rubric.version,
        focus_capability_key=focus,
        recalls=tuple(
            PlannedRecall(
                i.id,
                i.form,
                i.meaning,
                i.kind,
                i.capability_keys,
                last_support.get(i.id, "unknown"),
            )
            for i in chosen
        ),
        new_item_allowance=NewItemAllowance(allowance),
    )
