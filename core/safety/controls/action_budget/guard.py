from __future__ import annotations

from math import isfinite

from ..action_catalog import ActionSafetyCatalog, build_default_action_catalog
from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .ledger import ActionBudgetLedger
from .models import (
    ActionBudget,
    is_budget_free_read_projection,
    is_budget_free_text_message,
    is_routine_reply,
    telegram_action_fingerprint,
    verified_telegram_idempotency_key,
)


class ActionBudgetGuard:
    control_name = "action_budget"

    def __init__(self, ledger: ActionBudgetLedger, default_budget: ActionBudget, catalog: ActionSafetyCatalog | None = None):
        self._ledger = ledger
        self._default_budget = default_budget
        self._catalog = catalog or build_default_action_catalog()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        payload = dict(ctx.payload)
        try:
            raw_cost = payload.get("estimated_cost", 0)
            cost = float(raw_cost)
            if isinstance(raw_cost, bool) or not isfinite(cost) or cost < 0:
                raise ValueError("invalid estimated cost")
        except (TypeError, ValueError, OverflowError):
            return ControlDecision(self.control_name, ControlStatus.BLOCK, "action_budget_invalid_cost", {})
        idempotency_key = verified_telegram_idempotency_key(payload)
        if idempotency_key:
            lookup = getattr(self._ledger, "recorded_action", None)
            previous = lookup(ctx.tenant_id, idempotency_key) if callable(lookup) else None
            if previous is not None:
                expected = (str(ctx.action), telegram_action_fingerprint(ctx.action, payload))
                same_action = tuple(previous) == expected
                return ControlDecision(
                    self.control_name,
                    ControlStatus.ALLOW if same_action else ControlStatus.BLOCK,
                    "action_budget_replay_already_accounted" if same_action else "action_budget_idempotency_conflict",
                    {"idempotent_replay": same_action},
                )
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
        next_cost = current_cost + (cost if "estimated_cost" in payload else default_cost)
        if not all(isfinite(v) and v >= 0 for v in (current_cost, default_cost, next_cost)):
            return ControlDecision(self.control_name, ControlStatus.BLOCK, "action_budget_invalid_cost", {})
        next_actions = current_actions + 1
        exceeded = next_cost > self._default_budget.max_cost or next_actions > self._default_budget.max_actions
        return ControlDecision(
            control=self.control_name,
            status=ControlStatus.BLOCK if exceeded else ControlStatus.ALLOW,
            reason="action_budget_exceeded" if exceeded else "action_budget_ok",
            details={"next_cost": next_cost, "next_actions": next_actions},
        )
