from __future__ import annotations

from ..action_catalog import ActionSafetyCatalog, build_default_action_catalog
from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .ledger import ActionBudgetLedger
from .models import ActionBudget, is_routine_reply


class ActionBudgetGuard:
    control_name = "action_budget"

    def __init__(self, ledger: ActionBudgetLedger, default_budget: ActionBudget, catalog: ActionSafetyCatalog | None = None):
        self._ledger = ledger
        self._default_budget = default_budget
        self._catalog = catalog or build_default_action_catalog()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        payload = dict(ctx.payload)
        if is_routine_reply(ctx.action, payload):
            # Service replies cannot exhaust the lifetime budget intended for
            # effectful business actions, but retain a bounded daily quota.
            counter = getattr(self._ledger, "routine_reply_count", None)
            if not callable(counter):
                return ControlDecision(
                    control=self.control_name, status=ControlStatus.BLOCK,
                    reason="routine_reply_budget_unavailable", details={},
                )
            next_actions = counter(ctx.tenant_id) + 1
            if next_actions > self._default_budget.max_actions:
                return ControlDecision(
                    control=self.control_name, status=ControlStatus.BLOCK,
                    reason="action_budget_exceeded",
                    details={"next_actions": next_actions, "budget_class": "routine_reply_utc_day"},
                )
            return ControlDecision(
                control=self.control_name, status=ControlStatus.ALLOW,
                reason="action_budget_ok",
                details={"next_actions": next_actions, "budget_class": "routine_reply_utc_day"},
            )
        current_cost, current_actions = self._ledger.snapshot(ctx.tenant_id)
        spec = self._catalog.resolve(ctx.action)
        default_cost = float(getattr(spec, "default_estimated_cost", 0.0) or 0.0)
        incremental_cost = float(payload.get("estimated_cost", default_cost) or default_cost)
        next_cost = current_cost + incremental_cost
        next_actions = current_actions + 1
        if next_cost > self._default_budget.max_cost or next_actions > self._default_budget.max_actions:
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.BLOCK,
                reason="action_budget_exceeded",
                details={"next_cost": next_cost, "next_actions": next_actions},
            )
        return ControlDecision(
            control=self.control_name,
            status=ControlStatus.ALLOW,
            reason="action_budget_ok",
            details={"next_cost": next_cost, "next_actions": next_actions},
        )
