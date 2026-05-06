from __future__ import annotations
from execution.routing.capability_registry import CapabilityRoute
CANON_CAPABILITY_PROOFABILITY_SCORE = True
class CapabilityProofabilityScore:
    def score(self, *, route: CapabilityRoute, externally_verified: bool, prod_ready: bool) -> float:
        base = max(0.0, min(1.0, float(route.base_proofability)))
        if externally_verified:
            base = max(base, 0.70)
        if prod_ready:
            base = min(1.0, base + 0.10)
        return max(0.0, min(1.0, base))
