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
