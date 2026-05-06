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

BANNED_RETURN_NAMES = {
    "DecisionCommand",
    "ExecutionResult",
    "ExecutionResponse",
    "GatewayResponse",
    "ConnectorResponse",
}


def _return_names(tree: ast.AST) -> list[str]:
    names: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.returns is None:
            continue

        if isinstance(node.returns, ast.Name):
            names.append(node.returns.id)
        elif isinstance(node.returns, ast.Attribute):
            names.append(node.returns.attr)

    return names


def test_recommendation_stage_modules_do_not_return_execution_objects() -> None:
    offenders: dict[str, list[str]] = {}

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        bad = sorted({name for name in _return_names(tree) if name in BANNED_RETURN_NAMES})

        if bad:
            offenders[rel] = bad

    assert not offenders, (
        "Recommendation-stage modules may not return execution-oriented objects. "
        f"Offenders: {offenders}"
    )
