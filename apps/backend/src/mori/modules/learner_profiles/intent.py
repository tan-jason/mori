"""Validation for learner-authored goals and speaking context."""

from __future__ import annotations

import tiktoken

MAX_INTENT_TOKENS = 1_000
MAX_GOAL_CHARS = 500
MAX_SPEAKING_CONTEXT_CHARS = 500
MAX_NOTES_CHARS = 3_000
MAX_INTENT_CHARS = 3_000
_ENCODING = tiktoken.get_encoding("o200k_base")


def normalize_intent(goal: str, speaking_context: str, notes: str) -> tuple[str, str, str]:
    goal = " ".join(goal.split())
    speaking_context = " ".join(speaking_context.split())
    notes = " ".join(notes.split())
    if not 1 <= len(goal) <= MAX_GOAL_CHARS:
        raise ValueError("learning goal must contain 1 to 500 characters")
    if not 1 <= len(speaking_context) <= MAX_SPEAKING_CONTEXT_CHARS:
        raise ValueError("speaking context must contain 1 to 500 characters")
    if len(notes) > MAX_NOTES_CHARS:
        raise ValueError("learning notes must contain at most 3000 characters")
    if sum(map(len, (goal, speaking_context, notes))) > MAX_INTENT_CHARS:
        raise ValueError("learning context must contain at most 3000 characters")
    token_count = sum(len(_ENCODING.encode(value)) for value in (goal, speaking_context, notes))
    if token_count > MAX_INTENT_TOKENS:
        raise ValueError("learning context must contain at most 1000 tokens")
    return goal, speaking_context, notes
