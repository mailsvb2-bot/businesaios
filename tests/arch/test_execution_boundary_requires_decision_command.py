from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "runtime" / "handlers" / "ads_autopilot_flow.py"


def _annotation_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def test_execution_boundary_requires_decision_command() -> None:
    if not TARGET.exists():
        return

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "execution" not in node.name:
            continue

        has_decision_command = False

        for arg in node.args.args:
            if arg.annotation is None:
                continue
            if _annotation_name(arg.annotation) == "DecisionCommand":
                has_decision_command = True
                break

        if not has_decision_command:
            offenders.append(node.name)

    assert not offenders, (
        "Execution boundary functions must require DecisionCommand explicitly. "
        f"Offenders: {offenders}"
    )
