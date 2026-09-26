from __future__ import annotations

from execution.autonomy_tiers import CANONICAL_AUTONOMY_TIERS, evaluate_autonomy_tier, normalize_autonomy_tier
from execution.headless_contract import GoalExecutionRequest




def test_goal_execution_request_accepts_uppercase_canonical_and_legacy_tiers() -> None:
    for tier in ("OBSERVE", "ADVISORY", "DRAFT", "APPROVAL_REQUIRED", "SUPERVISED", "AUTONOMOUS_BOUNDED", "bounded_autonomy", "full_autonomy"):
        ok, issues = GoalExecutionRequest(goal="x", business_id="biz", autonomy_tier=tier).validate()
        assert ok is True, (tier, issues)


def test_goal_execution_request_validates_autonomy_tier() -> None:
    ok, issues = GoalExecutionRequest(goal='x', business_id='biz', autonomy_tier='oops').validate()
    assert ok is False
    assert 'invalid:autonomy_tier' in issues


def test_autonomous_bounded_blocks_ads_write() -> None:
    decision = evaluate_autonomy_tier(action_type='launch_campaign', autonomy_tier='autonomous_bounded')
    assert decision.tier == 'autonomous_bounded'
    assert decision.blocked_by_policy is True
    assert decision.approval_required is False


def test_supervised_requires_approval_for_ads_write() -> None:
    decision = evaluate_autonomy_tier(action_type='launch_campaign', autonomy_tier='supervised')
    assert decision.blocked_by_policy is False
    assert decision.approval_required is True


def test_canonical_autonomy_taxonomy_is_exactly_six_levels() -> None:
    assert CANONICAL_AUTONOMY_TIERS == (
        "observe",
        "advisory",
        "draft",
        "approval_required",
        "supervised",
        "autonomous_bounded",
    )


def test_legacy_autonomy_inputs_normalize_without_extra_authority() -> None:
    assert normalize_autonomy_tier("bounded_autonomy") == "autonomous_bounded"
    assert normalize_autonomy_tier("full_autonomy") == "autonomous_bounded"


def test_observe_and_advisory_never_authorize_effectful_actions() -> None:
    for tier in ("observe", "advisory"):
        decision = evaluate_autonomy_tier(action_type="reply_to_inquiry", autonomy_tier=tier)
        assert decision.tier == tier
        assert decision.allowed is False
        assert decision.blocked_by_policy is True


def test_draft_allows_internal_preparation_but_blocks_external_effect() -> None:
    internal = evaluate_autonomy_tier(action_type="notify_owner", autonomy_tier="draft")
    external = evaluate_autonomy_tier(action_type="reply_to_inquiry", autonomy_tier="draft")
    assert internal.action_class == "internal_execution"
    assert internal.allowed is True
    assert external.allowed is False
    assert external.blocked_by_policy is True


def test_approval_required_hands_effectful_action_to_human() -> None:
    decision = evaluate_autonomy_tier(action_type="reply_to_inquiry", autonomy_tier="approval_required")
    assert decision.allowed is False
    assert decision.approval_required is True
    assert decision.blocked_by_policy is False
