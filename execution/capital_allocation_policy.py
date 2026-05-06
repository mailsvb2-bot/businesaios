from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.business_roi_registry import BusinessROISignal

CANON_CAPITAL_ALLOCATION_POLICY = True


def _clamp(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


@dataclass(frozen=True, slots=True)
class CapitalAllocationDecision:
    business_key: str
    target_share: float
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"business_key": self.business_key, "target_share": float(self.target_share), "rationale": self.rationale, "metadata": dict(self.metadata)}


class CapitalAllocationPolicy:
    def allocate(self, *, signals: tuple[BusinessROISignal, ...]) -> tuple[CapitalAllocationDecision, ...]:
        if not signals:
            return ()
        weights = [max(0.0, s.adjusted_roi) * max(0.1, s.confidence) for s in signals]
        total = sum(weights) or float(len(signals))
        return tuple(
            CapitalAllocationDecision(
                business_key=s.business_key,
                target_share=_clamp(weight / total),
                rationale="roi_weighted_allocation",
                metadata={"owner": "execution.capital_allocation_policy"},
            )
            for s, weight in zip(signals, weights)
        )


__all__ = ["CANON_CAPITAL_ALLOCATION_POLICY", "CapitalAllocationDecision", "CapitalAllocationPolicy"]
