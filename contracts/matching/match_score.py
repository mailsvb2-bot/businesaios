from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MatchScore:
    business_id: str = ""
    metric: str = ""
    value: float = 0.0
    weight: float = 0.0
    reason: str = ""
