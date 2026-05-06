from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_PACKAGES = {"application", "config", "core", "runtime", "execution", "entrypoints", "kernel", "billing", "tenancy"}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_sitecustomize_does_not_import_project_packages() -> None:
    assert imported_roots(PROJECT_ROOT / "sitecustomize.py").isdisjoint(PROJECT_PACKAGES)


def test_usercustomize_does_not_import_project_packages() -> None:
    assert imported_roots(PROJECT_ROOT / "usercustomize.py").isdisjoint(PROJECT_PACKAGES)
