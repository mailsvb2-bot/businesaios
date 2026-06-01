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

BANNED_SERIALIZERS = {
    "dump",
    "dumps",
    "serialize",
    "to_json",
    "asdict",
}


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def test_recommendation_stage_does_not_serialize_transport_bridges() -> None:
    offenders: dict[str, list[str]] = {}

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _called_name(node)
                if name in BANNED_SERIALIZERS:
                    found.append(name)

        if found:
            offenders[rel] = sorted(set(found))

    assert not offenders, (
        "Recommendation-stage modules may not serialize payload bridges for downstream execution. "
        f"Offenders: {offenders}"
    )
