from boot.registrations.simple_singletons import ActionBudget, RewardGuard, RiskEngine


def test_action_budget_uses_canonical_default_limit():
    assert ActionBudget().max_actions == 1000


def test_reward_guard_defaults_remain_canonical():
    guard = RewardGuard()
    assert guard.min_reward == -0.25
    assert guard.min_margin == 0.0


def test_risk_engine_defaults_are_bounded():
    engine = RiskEngine()
    assert 0.0 <= engine.default_high_risk_score <= 1.0
    assert 0.0 <= engine.elevated_risk_score <= 1.0
