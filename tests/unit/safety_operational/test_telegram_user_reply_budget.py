from __future__ import annotations

from contracts.action_impact_contract import ActionExecutionContext
from core.safety.operational.action_classifier import ActionClassifier
from core.safety.operational.action_cost_model import ActionCostModel
from core.safety.operational.action_impact_builder import ActionImpactBuilder
from core.safety.operational.action_registry import (
    TELEGRAM_INTERACTIVE_ACTION_DESCRIPTORS,
    build_default_operational_action_registry,
)
from core.safety.operational.operational_budget_accountant import OperationalBudgetAccountant


def _envelope(action: str):
    builder = ActionImpactBuilder(ActionClassifier(build_default_operational_action_registry()), ActionCostModel())
    ctx = ActionExecutionContext(
        tenant_id="t1", user_id="u1", action_name=action, payload={"safety_now": "2026-10-23T10:00:00+00:00"}
    )
    impact = builder.build(ctx)
    return OperationalBudgetAccountant().to_envelope(ctx, impact)


def test_every_telegram_user_reply_is_free_of_tenant_autonomy_budget() -> None:
    for name in TELEGRAM_INTERACTIVE_ACTION_DESCRIPTORS:
        env = _envelope(name)
        assert (env.actions_count, env.outbound_count, env.approval_required_without_human) == (0, 0, 0), name


def test_autonomous_outbound_still_counts() -> None:
    env = _envelope("send_message@v1")
    assert env.actions_count == 1 and env.outbound_count == 1
