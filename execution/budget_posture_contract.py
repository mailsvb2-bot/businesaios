from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CANON_BUDGET_POSTURE_CONTRACT = True


@dataclass(frozen=True)
class BudgetPostureRecommendation:
    posture: str = "neutral"
    cost_multiplier: float = 1.0
    total_budget_multiplier: float = 1.0
    outbound_multiplier: float = 1.0
    publication_multiplier: float = 1.0
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'posture': str(self.posture),
            'cost_multiplier': float(self.cost_multiplier),
            'total_budget_multiplier': float(self.total_budget_multiplier),
            'outbound_multiplier': float(self.outbound_multiplier),
            'publication_multiplier': float(self.publication_multiplier),
            'confidence': float(self.confidence),
            'reasons': list(self.reasons),
            'metadata': dict(self.metadata),
        }


__all__ = ['CANON_BUDGET_POSTURE_CONTRACT', 'BudgetPostureRecommendation']
