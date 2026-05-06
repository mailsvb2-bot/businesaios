from __future__ import annotations

from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .executor import PredicateSandboxExecutor


class DecisionSandboxGuard:
    control_name = "decision_sandbox"

    def __init__(self, executor: PredicateSandboxExecutor):
        self._executor = executor

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        outcome = self._executor.run(ctx)
        if not outcome.passed:
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.BLOCK,
                reason="sandbox_failed",
                details={"findings": list(outcome.findings), "evidence": outcome.evidence},
            )
        return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason="sandbox_passed")
