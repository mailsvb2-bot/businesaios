from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "runtime" / "handlers" / "ads_autopilot_flow.py"


def test_execution_boundary_runs_service_with_explicit_command_variable() -> None:
    if not TARGET.exists():
        return

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "execution" not in node.name:
            continue

        bad = False

        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            if not isinstance(inner.func, ast.Attribute):
                continue
            if inner.func.attr != "run":
                continue
            if len(inner.args) != 1:
                bad = True
                break
            arg = inner.args[0]
            if not isinstance(arg, ast.Name):
                bad = True
                break
            if arg.id != "command":
                bad = True
                break

        if bad:
            offenders.append(node.name)

    assert not offenders, (
        "Execution boundary must call service.run(command) with explicit canonical command variable. "
        f"Offenders: {offenders}"
    )
