from __future__ import annotations
from execution.routing.capability_registry import CapabilityRoute
CANON_FALLBACK_TREE = True
class FallbackTree:
    def next_candidates(self, *, routes: tuple[CapabilityRoute, ...], selected_route_key: str | None) -> tuple[CapabilityRoute, ...]:
        return tuple(route for route in routes if route.route_key != selected_route_key)
