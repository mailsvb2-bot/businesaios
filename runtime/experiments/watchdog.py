from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event

from core.experiments.guardrails import CanaryDecision, GuardrailResult
from runtime.experiments.live_canary import LiveCanaryCoordinator

log = logging.getLogger(__name__)
RollbackSubmitter = Callable[..., None]


class LiveCanaryWatchdog:
    """Evaluate evidence and submit rollback through RuntimeExecutor governance."""

    def __init__(
        self,
        coordinator: LiveCanaryCoordinator,
        *,
        tenant_id: str,
        rollback_submitter: RollbackSubmitter,
        interval_seconds: float = 60.0,
    ) -> None:
        if interval_seconds < 1:
            raise ValueError("interval_seconds must be at least one")
        if not callable(rollback_submitter):
            raise TypeError("rollback_submitter must be callable")
        self.coordinator = coordinator
        self.tenant_id = str(tenant_id)
        self.rollback_submitter = rollback_submitter
        self.interval_seconds = float(interval_seconds)
        self._sequence = 0

    def run_once(self) -> GuardrailResult:
        self._sequence += 1
        decision_id = f"live-canary-watchdog:{self._sequence}"
        correlation_id = f"live-canary:{self.coordinator.policy.experiment_id}"
        result = self.coordinator._guard_result()
        if result.decision is CanaryDecision.ROLLBACK:
            self.coordinator._open_local_circuit(
                result,
                decision_id=decision_id,
                correlation_id=correlation_id,
                tenant_id=self.tenant_id,
            )
            self.rollback_submitter(
                decision_id=decision_id,
                correlation_id=correlation_id,
                tenant_id=self.tenant_id,
                candidate_policy_id=self.coordinator.candidate_policy_id,
                experiment_id=self.coordinator.policy.experiment_id,
                reasons=result.reasons,
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


__all__ = ["LiveCanaryWatchdog", "RollbackSubmitter"]
