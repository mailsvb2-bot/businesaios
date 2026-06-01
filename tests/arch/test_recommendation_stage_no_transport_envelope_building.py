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

BANNED_DICT_KEYS = {
    "action",
    "route",
    "issuer_id",
    "decision_id",
    "command",
    "commands",
    "execute",
    "execution",
    "launch",
    "apply",
}


def _dict_string_keys(node: ast.Dict) -> set[str]:
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return keys


def test_recommendation_stage_does_not_build_execution_transport_envelopes() -> None:
    offenders: dict[str, list[str]] = {}

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                keys = _dict_string_keys(node)
                bad = sorted(keys & BANNED_DICT_KEYS)
                found.extend(bad)

        if found:
            offenders[rel] = sorted(set(found))

    assert not offenders, (
        "Recommendation-stage modules may not build execution-like transport envelopes. "
        f"Offenders: {offenders}"
    )
