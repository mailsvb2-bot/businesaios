from __future__ import annotations
from execution.routing.capability_registry import CapabilityRoute
CANON_CAPABILITY_LATENCY_MODEL = True
class CapabilityLatencyModel:
    def score(self, *, route: CapabilityRoute) -> float:
        latency = max(0.0, float(route.base_latency_ms))
        return 1.0 / (1.0 + (latency / 1000.0))
