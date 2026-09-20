"""Executable module-boundary rules for the modular monolith."""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "mori"
FORBIDDEN_DOMAIN_ROOTS = {
    "alembic",
    "authlib",
    "fastapi",
    "httpx",
    "httpx2",
    "pydantic",
    "sqlalchemy",
    "starlette",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_domain_modules_do_not_import_frameworks_or_adapters() -> None:
    for path in (SOURCE_ROOT / "modules").glob("*/domain.py"):
        roots = {name.partition(".")[0] for name in _imports(path)}
        assert roots.isdisjoint(FORBIDDEN_DOMAIN_ROOTS), f"{path} imports a framework or adapter"


def test_routes_do_not_import_persistence_entities() -> None:
    for path in (SOURCE_ROOT / "modules").glob("*/routes.py"):
        imports = _imports(path)
        forbidden = {name for name in imports if name.endswith((".models", ".persistence"))}
        assert not forbidden, f"{path} bypasses its application boundary: {sorted(forbidden)}"
