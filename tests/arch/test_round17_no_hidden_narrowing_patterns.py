from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SENSITIVE_PREFIXES = ("core/growth/", "core/reward/", "core/economics/", "core/ml/", "ml/", "runtime/")
FORBIDDEN_TARGETS = {"default_action", "final_action", "resolved_action", "recommended_action"}


def _assigned_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {name for item in target.elts for name in _assigned_names(item)}
    return set()


def test_no_hidden_narrowing_patterns_in_sensitive_areas() -> None:
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("tests/", "docs/")) or not rel.startswith(SENSITIVE_PREFIXES):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=rel)
        for node in ast.walk(tree):
            names: set[str] = set()
            value = None
            if isinstance(node, ast.Assign):
                names = {name for target in node.targets for name in _assigned_names(target)}
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                names = _assigned_names(node.target)
                value = node.value
            if names & FORBIDDEN_TARGETS:
                offenders.append(f"{rel}:{getattr(node, 'lineno', 0)}:{sorted(names & FORBIDDEN_TARGETS)}")
                continue
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "next":
                if any("action" in name.lower() for name in names):
                    offenders.append(f"{rel}:{getattr(node, 'lineno', 0)}:next-action")
    assert not offenders, f"forbidden hidden narrowing found: {offenders}"
