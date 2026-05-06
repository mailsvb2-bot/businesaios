from __future__ import annotations

from core.policies.domain import RolloutConfig
from core.policies.metrics import CanaryMetrics


class SafetyEvaluator:
    def __init__(self, cfg: RolloutConfig):
        self.cfg = cfg

    def evaluate(self, m: CanaryMetrics) -> str:
        if m.decisions < self.cfg.min_decisions:
            return "continue"

        if m.error_rate > self.cfg.max_error_rate:
            return "rollback"

        return "promote" if self.cfg.auto_promote else "continue"
