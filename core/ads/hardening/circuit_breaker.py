"""Ads HTTP circuit breaker.

Per-platform circuit breaker. Opens after N consecutive failures,
half-opens after cooldown, closes on success.

Patch 10.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from config.ads_hardening_policy import (
    DEFAULT_ADS_CIRCUIT_BREAKER_POLICY,
    AdsCircuitBreakerPolicy,
)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _Circuit:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    last_failure: float = DEFAULT_ADS_CIRCUIT_BREAKER_POLICY.last_failure_zero
    threshold: int = DEFAULT_ADS_CIRCUIT_BREAKER_POLICY.threshold
    cooldown_s: float = DEFAULT_ADS_CIRCUIT_BREAKER_POLICY.cooldown_s

    def record_success(self) -> None:
        self.failures = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure = time.monotonic()
        if self.failures >= self.threshold:
            self.state = CircuitState.OPEN

    def can_proceed(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure > self.cooldown_s:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one probe
        return True


class AdsCircuitBreaker:
    """Per-platform circuit breaker."""

    def __init__(
        self,
        *,
        threshold: int | None = None,
        cooldown_s: float | None = None,
        policy: AdsCircuitBreakerPolicy = DEFAULT_ADS_CIRCUIT_BREAKER_POLICY,
    ) -> None:
        self._policy = policy
        self._threshold = int(policy.threshold if threshold is None else threshold)
        self._cooldown_s = float(policy.cooldown_s if cooldown_s is None else cooldown_s)
        self._circuits: dict[str, _Circuit] = {}

    def _get(self, platform: str) -> _Circuit:
        if platform not in self._circuits:
            self._circuits[platform] = _Circuit(
                threshold=self._threshold,
                cooldown_s=self._cooldown_s,
            )
        return self._circuits[platform]

    def can_proceed(self, platform: str) -> bool:
        return self._get(platform).can_proceed()

    def record_success(self, platform: str) -> None:
        self._get(platform).record_success()

    def record_failure(self, platform: str) -> None:
        self._get(platform).record_failure()

    def assert_can_proceed(self, platform: str) -> None:
        if not self.can_proceed(platform):
            raise RuntimeError(f"ADS_CIRCUIT_OPEN: platform={platform}")
