from __future__ import annotations

from execution.autonomy_tiers import evaluate_autonomy_tier
from execution.headless_contract import GoalExecutionRequest


def test_goal_execution_request_validates_autonomy_tier() -> None:
    ok, issues = GoalExecutionRequest(goal='x', business_id='biz', autonomy_tier='oops').validate()
    assert ok is False
    assert 'invalid:autonomy_tier' in issues


def test_bounded_autonomy_blocks_ads_write() -> None:
    decision = evaluate_autonomy_tier(action_type='launch_campaign', autonomy_tier='bounded_autonomy')
    assert decision.blocked_by_policy is True
    assert decision.approval_required is False


def test_supervised_requires_approval_for_ads_write() -> None:
    decision = evaluate_autonomy_tier(action_type='launch_campaign', autonomy_tier='supervised')
    assert decision.blocked_by_policy is False
    assert decision.approval_required is True
