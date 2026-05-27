from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    kind: str
    score: float
    channel: str
    expected_value: float = 0.0
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
