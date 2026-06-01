from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    business_id: str = ""
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()
    blocked: bool = False
