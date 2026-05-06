from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

TARGETS = (
    "core/economics/brain.py",
    "core/economics/capital_engine.py",
    "core/economics/capital_allocation_engine.py",
    "core/growth/autopilot_engine.py",
    "runtime/handlers/ads_autopilot_flow_service.py",
)

BANNED_ANNOTATIONS = {
    "DecisionExecutionService",
    "ExecutionService",
    "Gateway",
    "Client",
    "Connector",
    "Repository",
}


def _annotation_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def test_recommendation_stage_modules_do_not_accept_execution_dependencies() -> None:
    offenders: dict[str, list[str]] = {}

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            for arg in node.args.args:
                if arg.annotation is None:
                    continue

                name = _annotation_name(arg.annotation)
                if name in BANNED_ANNOTATIONS:
                    found.append(f"{node.name}:{name}")

        if found:
            offenders[rel] = found

    assert not offenders, (
        "Recommendation-stage modules may not accept execution or connector dependencies. "
        f"Offenders: {offenders}"
    )
