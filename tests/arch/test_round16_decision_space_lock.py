from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_capability_vocabulary_exists():
    text = (ROOT / "core/decisioning/capability_vocabulary.py").read_text(encoding="utf-8")
    assert "Capability(" in text


def test_candidate_space_helper_exists():
    text = (ROOT / "core/decisioning/candidate_space.py").read_text(encoding="utf-8")
    assert "CandidateScore" in text


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return {name for item in node.elts for name in _target_names(item)}
    return set()


def test_no_hidden_next_pattern():
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=rel)
        for node in ast.walk(tree):
            target_names: set[str] = set()
            value = None
            if isinstance(node, ast.Assign):
                target_names = {name for target in node.targets for name in _target_names(target)}
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                target_names = _target_names(node.target)
                value = node.value
            if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != "next":
                continue
            if any("action" in name.lower() or "decision" in name.lower() for name in target_names):
                offenders.append(f"{rel}:{getattr(node, 'lineno', 0)}")
    assert not offenders, f"hidden action narrowing found: {offenders}"
