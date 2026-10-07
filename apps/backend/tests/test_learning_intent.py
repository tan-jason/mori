"""Bounds for learner-authored context included in every realtime prompt."""

import pytest

from mori.modules.learner_profiles.intent import normalize_intent


def test_learning_intent_normalizes_whitespace() -> None:
    assert normalize_intent(" Talk  with family ", " Casual   chats ", "  ") == (
        "Talk with family", "Casual chats", ""
    )


def test_learning_intent_rejects_empty_and_over_token_budget() -> None:
    with pytest.raises(ValueError, match="learning goal"):
        normalize_intent(" ", "Casual chats", "")
    with pytest.raises(ValueError, match="1000 tokens"):
        normalize_intent("Talk with family", "Casual chats", "字" * 1500)
