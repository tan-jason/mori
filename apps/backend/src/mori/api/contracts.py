"""OpenAPI declarations for headers checked by the existing request guards."""

from __future__ import annotations

from typing import Any


def mutation_headers(*names: str) -> dict[str, Any]:
    return {
        "parameters": [
            {
                "in": "header",
                "name": name,
                "required": True,
                "schema": {"type": "string"},
            }
            for name in ("X-CSRF-Token", *names)
        ]
    }
