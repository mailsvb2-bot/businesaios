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

BANNED_NAME_PARTS = (
    "helper",
    "helpers",
    "util",
    "utils",
    "gateway",
    "client",
    "connector",
    "adapter",
    "dispatcher",
    "publisher",
    "executor",
    "runner",
)


def _is_banned_name(name: str) -> bool:
    lowered = name.lower()
    return any(part in lowered for part in BANNED_NAME_PARTS)


def test_recommendation_stage_modules_do_not_import_hidden_side_effect_helpers() -> None:
    offenders: dict[str, list[str]] = {}

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if _is_banned_name(node.module):
                    found.append(node.module)

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_banned_name(alias.name):
                        found.append(alias.name)

        if found:
            offenders[rel] = sorted(set(found))

    assert not offenders, (
        "Recommendation-stage modules may not import hidden helper or connector style modules. "
        f"Offenders: {offenders}"
    )
