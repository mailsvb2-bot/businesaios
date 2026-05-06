from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

HOTSPOTS = (
    "core/economics/brain.py",
    "core/economics/capital_engine.py",
    "core/economics/capital_allocation_engine.py",
    "core/growth/autopilot_engine.py",
)


def test_hotspots_do_not_emit_decision_commands() -> None:
    offenders: list[str] = []

    for rel in HOTSPOTS:
        path = ROOT / rel
        if not path.exists():
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        if "DecisionCommand" in names:
            offenders.append(rel)

    assert not offenders, (
        "Hotspot modules must not emit DecisionCommand. "
        f"Offenders: {offenders}"
    )
