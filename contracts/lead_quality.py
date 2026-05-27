from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LeadQuality:
    score: float = 0.0
    confidence: float = 0.0
    reason: str = ''
