from __future__ import annotations

from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .analyzer import StaticBlastRadiusAnalyzer
from .policy import BlastRadiusPolicy


class BlastRadiusGuard:
    control_name = "blast_radius"

    def __init__(self, policy: BlastRadiusPolicy, analyzer: StaticBlastRadiusAnalyzer | None = None):
        self._policy = policy
        self._analyzer = analyzer or StaticBlastRadiusAnalyzer()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        budget = self._policy.budget_for(ctx.action)
        estimate = self._analyzer.estimate(ctx)
        exceeded = {
            "financial_amount": estimate.financial_amount > budget.financial_amount,
            "users_affected": estimate.users_affected > budget.users_affected,
            "records_affected": estimate.records_affected > budget.records_affected,
            "services_touched": estimate.services_touched > budget.services_touched,
        }
        if any(exceeded.values()):
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.BLOCK,
                reason="blast_radius_exceeded",
                details={"estimate": estimate.__dict__, "budget": budget.__dict__, "exceeded": exceeded},
            )
        return ControlDecision(
            control=self.control_name,
            status=ControlStatus.ALLOW,
            reason="within_blast_radius",
            details={"estimate": estimate.__dict__, "budget": budget.__dict__},
        )
