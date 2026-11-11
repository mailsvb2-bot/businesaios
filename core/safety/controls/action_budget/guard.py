from __future__ import annotations

from ..action_catalog import ActionSafetyCatalog, build_default_action_catalog
from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .ledger import ActionBudgetLedger
from .models import ActionBudget, is_budget_free_text_message, is_routine_reply, is_budget_free_read_projection


class ActionBudgetGuard:
    control_name = "action_budget"

    def __init__(self, ledger: ActionBudgetLedger, default_budget: ActionBudget, catalog: ActionSafetyCatalog | None = None):
        self._ledger = ledger
        self._default_budget = default_budget
        self._catalog = catalog or build_default_action_catalog()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        payload = dict(ctx.payload)
        if str(payload.get("tenant_id") or "") == str(ctx.tenant_id):
            for predicate, reason, budget_class in (
                (is_budget_free_text_message, "text_delivery_budget_not_applicable", "text_delivery"),
                (is_routine_reply, "user_reply_budget_not_applicable", "user_reply"),
                (is_budget_free_read_projection, "read_projection_budget_not_applicable", "read_projection"),
            ):
                if predicate(ctx.action, payload):
                    return ControlDecision(self.control_name, ControlStatus.ALLOW,
                                           reason, {"budget_class": budget_class})
        current_cost, current_actions = self._ledger.snapshot(ctx.tenant_id)
        spec = self._catalog.resolve(ctx.action)
        default_cost = float(getattr(spec, "default_estimated_cost", 0.0) or 0.0)
        next_cost = current_cost + float(payload.get("estimated_cost", default_cost) or default_cost)
        next_actions = current_actions + 1
        exceeded = next_cost > self._default_budget.max_cost or next_actions > self._default_budget.max_actions
        return ControlDecision(
            control=self.control_name,
            status=ControlStatus.BLOCK if exceeded else ControlStatus.ALLOW,
            reason="action_budget_exceeded" if exceeded else "action_budget_ok",
            details={"next_cost": next_cost, "next_actions": next_actions},
        )
