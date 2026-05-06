from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class DecisionContext:
    business_id: str
    region: str
    channel: str
    risk_level: str = 'medium'
    facts: Dict[str, Any] = field(default_factory=dict)
