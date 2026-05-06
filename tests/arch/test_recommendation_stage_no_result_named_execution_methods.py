from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

TARGETS = (
    "runtime/handlers/ads_autopilot_flow_service.py",
    "core/growth/autopilot_engine.py",
    "core/economics/brain.py",
    "core/economics/capital_engine.py",
    "core/economics/capital_allocation_engine.py",
)

SUSPICIOUS_PAIRS = (
    ("result", "run"),
    ("result", "execute"),
    ("result", "launch"),
    ("result", "apply"),
    ("payload", "run"),
    ("payload", "execute"),
    ("payload", "launch"),
    ("payload", "apply"),
    ("recommendation", "run"),
    ("recommendation", "execute"),
    ("recommendation", "launch"),
    ("recommendation", "apply"),
    ("recommendations", "run"),
    ("recommendations", "execute"),
    ("recommendations", "launch"),
    ("recommendations", "apply"),
)


def test_recommendation_stage_does_not_run_side_effects_from_result_like_names() -> None:
    offenders: dict[str, list[str]] = {}

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            continue

        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        found: list[str] = []

        for left, right in SUSPICIOUS_PAIRS:
            marker = f"{left}.{right}("
            if marker in source:
                found.append(marker)

        if found:
            offenders[rel] = sorted(set(found))

    assert not offenders, (
        "Recommendation-stage modules may not invoke execution-like methods from result/payload objects. "
        f"Offenders: {offenders}"
    )
