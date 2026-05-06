from __future__ import annotations

from dataclasses import dataclass, field

from config.growth_autopilot_policy import DEFAULT_GROWTH_AUTOPILOT_POLICY, GrowthAutopilotPolicy


@dataclass(frozen=True)
class AutopilotRunConfig:
    policy: GrowthAutopilotPolicy = field(default_factory=lambda: DEFAULT_GROWTH_AUTOPILOT_POLICY)
    max_applies_per_run: int = field(default_factory=lambda: DEFAULT_GROWTH_AUTOPILOT_POLICY.max_applies_per_run)
    trust_threshold: float = field(default_factory=lambda: DEFAULT_GROWTH_AUTOPILOT_POLICY.trust_threshold)
    breaker_enabled: bool = field(default_factory=lambda: DEFAULT_GROWTH_AUTOPILOT_POLICY.breaker_enabled)
    import_days: int = field(default_factory=lambda: DEFAULT_GROWTH_AUTOPILOT_POLICY.import_days)
    level: str = field(default_factory=lambda: DEFAULT_GROWTH_AUTOPILOT_POLICY.level)
    notify: bool = field(default_factory=lambda: DEFAULT_GROWTH_AUTOPILOT_POLICY.notify)
