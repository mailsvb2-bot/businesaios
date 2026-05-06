from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class RoutingCandidate:
    business_id: str = ""
    rank_score: float = 0.0
    policy_tags: tuple[str, ...] = ()
    trace: dict[str, object] = field(default_factory=dict)
    blocked: bool = False
