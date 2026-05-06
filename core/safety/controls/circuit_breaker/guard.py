from __future__ import annotations

from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .policy import CircuitBreakerPolicy
from .store import InMemoryCircuitBreakerStore


class CircuitBreakerGuard:
    control_name = "circuit_breaker"

    def __init__(self, store: InMemoryCircuitBreakerStore, policy: CircuitBreakerPolicy | None = None):
        self._store = store
        self._policy = policy or CircuitBreakerPolicy()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        key = f"{ctx.tenant_id}:{ctx.action}"
        state = self._store.get(key)
        if state.opened or state.consecutive_failures >= self._policy.max_consecutive_failures:
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.BLOCK,
                reason="circuit_open",
                details={"key": key, "failures": state.consecutive_failures},
            )
        return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason="circuit_closed", details={"key": key})
