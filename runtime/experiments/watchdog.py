from __future__ import annotations

import logging
from threading import Event

from core.experiments.guardrails import CanaryDecision, GuardrailResult
from runtime.experiments.live_canary import LiveCanaryCoordinator

log = logging.getLogger(__name__)


class LiveCanaryWatchdog:
    """Periodically evaluates live evidence and enforces rollback."""

    def __init__(
        self,
        coordinator: LiveCanaryCoordinator,
        *,
        tenant_id: str,
        interval_seconds: float = 60.0,
    ) -> None:
        if interval_seconds < 1:
            raise ValueError("interval_seconds must be at least one")
        self.coordinator = coordinator
        self.tenant_id = str(tenant_id)
        self.interval_seconds = float(interval_seconds)
        self._sequence = 0

    def run_once(self) -> GuardrailResult:
        self._sequence += 1
        result = self.coordinator.evaluate_and_maybe_rollback(
            decision_id=f"live-canary-watchdog:{self._sequence}",
            correlation_id=f"live-canary:{self.coordinator.policy.experiment_id}",
            tenant_id=self.tenant_id,
        )
        log.info(
            "live_canary_watchdog decision=%s reasons=%s",
            result.decision.value,
            ",".join(result.reasons),
        )
        return result

    def run_forever(self, stop: Event) -> CanaryDecision:
        last = CanaryDecision.CONTINUE
        while not stop.is_set():
            result = self.run_once()
            last = result.decision
            if last is CanaryDecision.ROLLBACK:
                return last
            stop.wait(self.interval_seconds)
        return last


__all__ = ["LiveCanaryWatchdog"]
