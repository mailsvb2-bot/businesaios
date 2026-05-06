from __future__ import annotations

import threading

from core.policies.domain import PolicyRef, RolloutConfig
from core.policies.evaluator import SafetyEvaluator
from core.policies.metrics import CanaryMetrics
from core.policies.registry import PolicyRegistry


class SafeRolloutManager:
    def __init__(self, registry: PolicyRegistry, cfg: RolloutConfig):
        self.registry = registry
        self.metrics = CanaryMetrics()
        self.eval = SafetyEvaluator(cfg)
        self._lock = threading.Lock()

    def start_canary(self, ref: PolicyRef) -> None:
        with self._lock:
            self.registry.start_canary(ref)
            self.metrics = CanaryMetrics()

    def record(self, error: bool) -> None:
        with self._lock:
            self.metrics.decisions += 1
            if error:
                self.metrics.errors += 1

    def record_decision(self, error: bool) -> None:
        return self.record(error)

    def tick(self) -> str:
        with self._lock:
            action = self.eval.evaluate(self.metrics)
            if action == "rollback":
                self.registry.rollback()
            elif action == "promote":
                canary = self.registry.canary()
                if canary:
                    self.registry.promote(canary)
            return action
