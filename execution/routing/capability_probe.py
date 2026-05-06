from __future__ import annotations
from dataclasses import dataclass
from execution.routing.capability_quarantine import CapabilityQuarantine
from execution.routing.capability_registry import CapabilityRoute
CANON_CAPABILITY_PROBE = True
@dataclass(frozen=True)
class CapabilityProbeResult:
    route_key: str
    available: bool
    reason: str
class CapabilityProbe:
    def __init__(self, *, quarantine: CapabilityQuarantine, min_health_score: float = 0.10) -> None:
        self._quarantine = quarantine
        self._min_health_score = max(0.0, min(1.0, float(min_health_score)))
    def probe(self, *, route: CapabilityRoute) -> CapabilityProbeResult:
        if not route.enabled:
            return CapabilityProbeResult(route_key=route.route_key, available=False, reason='route_disabled')
        if self._quarantine.is_quarantined(route_key=route.route_key):
            return CapabilityProbeResult(route_key=route.route_key, available=False, reason='route_quarantined')
        if float(route.health_score) <= self._min_health_score:
            return CapabilityProbeResult(route_key=route.route_key, available=False, reason='route_unhealthy')
        return CapabilityProbeResult(route_key=route.route_key, available=True, reason='route_available')
