from __future__ import annotations
from dataclasses import dataclass
CANON_ROUTING_CAPABILITY_HEALTH_SCORING = True
@dataclass(frozen=True)
class CapabilityHealthSignal:
    success_rate: float
    verification_rate: float
    transient_failure_rate: float
    saturation_rate: float
    @property
    def score(self) -> float:
        success = max(0.0, min(1.0, float(self.success_rate)))
        verification = max(0.0, min(1.0, float(self.verification_rate)))
        transient = max(0.0, min(1.0, float(self.transient_failure_rate)))
        saturation = max(0.0, min(1.0, float(self.saturation_rate)))
        raw = (success * 0.45) + (verification * 0.30) + ((1.0 - transient) * 0.15) + ((1.0 - saturation) * 0.10)
        return max(0.0, min(1.0, raw))
