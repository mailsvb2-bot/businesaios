from __future__ import annotations

import time
from dataclasses import dataclass

from config.circuit_breaker_policy import (
    DEFAULT_CIRCUIT_BREAKER_POLICY,
    CircuitBreakerPolicy,
)


@dataclass
class CircuitConfig:
    fail_threshold: int = DEFAULT_CIRCUIT_BREAKER_POLICY.fail_threshold
    open_for_s: float = DEFAULT_CIRCUIT_BREAKER_POLICY.open_for_s
    policy: CircuitBreakerPolicy = DEFAULT_CIRCUIT_BREAKER_POLICY

    def __post_init__(self) -> None:
        policy = self.policy or DEFAULT_CIRCUIT_BREAKER_POLICY
        self.fail_threshold = int(self.fail_threshold if self.fail_threshold is not None else policy.fail_threshold)
        self.open_for_s = float(self.open_for_s if self.open_for_s is not None else policy.open_for_s)


class CircuitBreaker:
    """Minimal circuit breaker.

    - opens after N consecutive failures
    - stays open for open_for_s seconds
    """

    def __init__(self, cfg: CircuitConfig) -> None:
        self._cfg = cfg
        self._fails = 0
        self._open_until = float(self._cfg.policy.closed_until_s)

    def is_open(self) -> bool:
        return time.time() < float(self._open_until)

    def on_success(self) -> None:
        self._fails = 0

    def on_failure(self) -> None:
        self._fails += 1
        if self._fails >= int(self._cfg.fail_threshold):
            self._open_until = time.time() + float(self._cfg.open_for_s)
            self._fails = 0
