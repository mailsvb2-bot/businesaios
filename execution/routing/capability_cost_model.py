from __future__ import annotations
from execution.routing.capability_registry import CapabilityRoute
CANON_CAPABILITY_COST_MODEL = True
class CapabilityCostModel:
    def score(self, *, route: CapabilityRoute, requested_units: float = 1.0) -> float:
        units = max(0.0, float(requested_units))
        effective_cost = max(0.0, float(route.base_cost) * units)
        if effective_cost <= 0.0:
            return 1.0
        return 1.0 / (1.0 + effective_cost)
