"""Bounded session setup shared by HTTP and orchestration."""

from __future__ import annotations


def normalize_topic(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 160 or any(ord(char) < 32 for char in normalized):
        raise ValueError("invalid session topic")
    return normalized


def normalize_requested_words(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(value) > 8:
        raise ValueError("too many requested words")
    normalized = tuple(" ".join(word.split()) for word in value)
    if any(
        not word or len(word) > 48 or any(ord(char) < 32 for char in word) for word in normalized
    ) or len({word.casefold() for word in normalized}) != len(normalized):
        raise ValueError("invalid requested words")
    return normalized
