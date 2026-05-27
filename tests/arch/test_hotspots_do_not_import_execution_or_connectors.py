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

BANNED_PREFIXES = (
    "runtime.execution",
    "interfaces.",
    "runtime.handlers",
)


def test_hotspots_do_not_import_execution_or_connectors() -> None:
    offenders: list[str] = []

    for rel in HOTSPOTS:
        path = ROOT / rel
        if not path.exists():
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        violated = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(BANNED_PREFIXES):
                    violated = True
                    break
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(BANNED_PREFIXES):
                        violated = True
                        break

        if violated:
            offenders.append(rel)

    assert not offenders, (
        "Hotspot modules may not import execution, handlers, or connectors directly. "
        f"Offenders: {offenders}"
    )
