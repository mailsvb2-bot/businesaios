from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGETS = (
    "core/economics/brain.py",
    "core/economics/capital_engine.py",
    "core/economics/capital_allocation_engine.py",
    "core/growth/autopilot_engine.py",
)


def _returns_recommendation_annotation(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.returns and isinstance(node.returns, ast.Name):
                if node.returns.id == "RecommendationSet":
                    return True
            if node.returns and isinstance(node.returns, ast.Subscript):
                value = node.returns.value
                if isinstance(value, ast.Name) and value.id == "RecommendationSet":
                    return True
    return False


def test_hotspots_expose_recommendation_return_types() -> None:
    offenders: list[str] = []

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not _returns_recommendation_annotation(tree):
            offenders.append(rel)

    assert not offenders, (
        "Hotspot APIs must visibly return RecommendationSet. "
        f"Offenders: {offenders}"
    )
