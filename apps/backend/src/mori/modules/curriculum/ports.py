"""Published course catalog query port."""

from __future__ import annotations

from typing import Protocol

from mori.modules.curriculum.domain import CoursePairView


class CourseCatalogStore(Protocol):
    async def language_pairs(self) -> tuple[CoursePairView, ...]: ...

    async def is_available(self, *, base_language_id: str, target_language_id: str) -> bool: ...
