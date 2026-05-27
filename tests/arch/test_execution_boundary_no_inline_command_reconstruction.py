from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "runtime" / "handlers" / "ads_autopilot_flow.py"


def test_execution_boundary_does_not_construct_command_inline() -> None:
    if not TARGET.exists():
        return

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "execution" not in node.name:
            continue

        violated = False

        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                if isinstance(inner.func, ast.Name) and inner.func.id == "DecisionCommand":
                    violated = True
                    break

        if violated:
            offenders.append(node.name)

    assert not offenders, (
        "Execution boundary must not reconstruct DecisionCommand inline. "
        "It must receive validated command from central decision layer. "
        f"Offenders: {offenders}"
    )
