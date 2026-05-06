from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse(path: pathlib.Path) -> ast.AST:
    return ast.parse(_read(path), filename=str(path))


def _iter_prod_py() -> list[pathlib.Path]:
    excluded = {"tests", "experimental", "docs", "ci", ".github", "data", "scripts", "canon"}
    files: list[pathlib.Path] = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("runtime/platform/support/"):
            continue
        if any(part in excluded for part in p.parts):
            continue
        files.append(p)
    return files


def _find_imports(path: pathlib.Path) -> set[str]:
    tree = _parse(path)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.add(n.name)
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports
