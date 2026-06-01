from __future__ import annotations

from typing import Iterable

CANONICAL_FLOW_STAGES: tuple[str, ...] = (
    "signal",
    "state",
    "decision",
    "policy_guard",
    "execution",
    "verification",
    "evidence",
    "memory_archive",
)

def is_canonical_flow_complete(stages: Iterable[str]) -> bool:
    seen = {str(item or "").strip() for item in stages}
    return all(stage in seen for stage in CANONICAL_FLOW_STAGES)
