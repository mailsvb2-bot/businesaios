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

BANNED_PREFIXES = (
    "runtime.execution",
    "interfaces.",
    "infrastructure.",
    "connectors.",
    "gateways.",
    "adapters.",
    "clients.",
)


def _has_banned_import(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith(BANNED_PREFIXES):
                return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(BANNED_PREFIXES):
                    return True
    return False


def test_recommendation_stage_modules_do_not_import_execution_layers() -> None:
    offenders: list[str] = []

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _has_banned_import(tree):
            offenders.append(rel)

    assert not offenders, (
        "Recommendation-stage modules may not import execution or connector layers. "
        f"Offenders: {offenders}"
    )
