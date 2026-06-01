from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "runtime" / "handlers" / "ads_autopilot_flow.py"

BANNED_ATTRS = {
    "action",
    "route",
    "issuer_id",
    "decision_id",
    "command",
    "commands",
}


def test_execution_boundary_does_not_reconstruct_decision_from_generic_objects() -> None:
    if not TARGET.exists():
        return

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    offenders: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "execution" not in node.name:
            continue

        found: list[str] = []

        for inner in ast.walk(node):
            if isinstance(inner, ast.Attribute):
                if inner.attr in BANNED_ATTRS:
                    found.append(inner.attr)

        if found:
            offenders[node.name] = sorted(set(found))

    assert not offenders, (
        "Execution boundary functions may not rebuild decision authority from generic object attributes. "
        f"Offenders: {offenders}"
    )
