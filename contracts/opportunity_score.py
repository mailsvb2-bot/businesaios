from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OpportunityScore:
    value: str = ''
    confidence: float = 0.0
    risk_penalty: str = ''
