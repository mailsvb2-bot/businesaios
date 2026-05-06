from __future__ import annotations

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from governance.change_control_policy import ChangeControlPolicy
from governance.rbac_contract import RoleId


def test_change_control_requires_dual_control_for_budget_change() -> None:
    policy = ChangeControlPolicy()
    decision = policy.evaluate(
        ctx=ActionExecutionContext(
            tenant_id="tenant-a",
            user_id="u1",
            action_name="change_budget",
            payload={},
            execution_id="exec-1",
        ),
        impact=ActionImpact(
            action_name="change_budget",
            category=ActionCategory.BUDGET_CHANGE,
            cost_minor=100_000,
        ),
    )
    assert decision.approval_required is True
    assert decision.required_role_groups == ((RoleId.OWNER,), (RoleId.FINANCE,))
    assert decision.min_distinct_approvers == 2


def test_change_control_fail_closed_for_unknown_category() -> None:
    policy = ChangeControlPolicy()
    decision = policy.evaluate(
        ctx=ActionExecutionContext(
            tenant_id="tenant-a",
            user_id="u1",
            action_name="mystery_action",
            payload={},
            execution_id="exec-2",
        ),
        impact=ActionImpact(
            action_name="mystery_action",
            category=ActionCategory.UNKNOWN,
        ),
    )
    assert decision.approval_required is True
    assert decision.reason == "unknown_action_category_fail_closed"
