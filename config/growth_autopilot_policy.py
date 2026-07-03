from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class GrowthAutopilotPolicy:
    max_applies_per_run: int = 3
    trust_threshold: float = 20.0
    breaker_enabled: bool = True
    import_days: int = 7
    level: str = "campaign"
    notify: bool = True


DEFAULT_GROWTH_AUTOPILOT_POLICY = GrowthAutopilotPolicy()
