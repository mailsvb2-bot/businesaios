from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.roi_predictor import ROIPrediction

CANON_ECONOMIC_SIMULATOR = True


@dataclass(frozen=True, slots=True)
class EconomicSimulation:
    requested_budget: float
    downside_revenue: float
    expected_revenue: float
    upside_revenue: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"requested_budget": float(self.requested_budget), "downside_revenue": float(self.downside_revenue), "expected_revenue": float(self.expected_revenue), "upside_revenue": float(self.upside_revenue), "metadata": dict(self.metadata)}


class EconomicSimulator:
    def simulate(self, *, requested_budget: float, prediction: ROIPrediction) -> EconomicSimulation:
        budget = max(0.0, float(requested_budget))
        return EconomicSimulation(
            requested_budget=budget,
            downside_revenue=max(0.0, budget * max(0.0, prediction.downside_roi)),
            expected_revenue=max(0.0, budget * max(0.0, prediction.expected_roi)),
            upside_revenue=max(0.0, budget * max(0.0, prediction.upside_roi)),
            metadata={"owner": "execution.economic_simulator"},
        )


__all__ = ["CANON_ECONOMIC_SIMULATOR", "EconomicSimulation", "EconomicSimulator"]
