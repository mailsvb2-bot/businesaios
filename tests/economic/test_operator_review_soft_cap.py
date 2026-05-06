from governance.economic.economic_policy_contract import EconomicPolicyConfig
from governance.economic.economic_policy_engine import EconomicPolicyEngine


class _Decision:
    action = "ads.scale_budget@v1"
    payload = {
        "channel": "ads",
        "economy": {
            "requested_budget": 900.0,
            "expected_incremental_gross_profit": 600.0,
            "expected_incremental_revenue": 1800.0,
            "expected_incremental_roi": 0.5,
            "priority": 70,
        },
    }


class _World:
    economics_state = {
        "cash_on_hand": 8000.0,
        "protected_cash_reserve": 1500.0,
        "available_liquidity": 7000.0,
        "monthly_burn": 1200.0,
        "gross_margin": 0.40,
        "target_margin": 0.30,
        "planned_spend": 1000.0,
        "hard_spend_cap": 0.0,
        "portfolio_budgets": {},
        "portfolio_weights": {"ads": 1.0, "seo": 0.8},
    }


def test_operator_review_when_near_soft_cap_but_not_over_hard_cap() -> None:
    config = EconomicPolicyConfig(
        spend_soft_cap_ratio=0.85,
        use_planned_spend_as_soft_cap_only=True,
    )
    engine = EconomicPolicyEngine(config=config)

    verdict = engine.review(_Decision(), _World())

    assert verdict.allowed is True
    assert verdict.operator_required is True
    assert verdict.reason == "budget_review:planned_spend_soft_cap_near_limit"
    assert "budget_review:planned_spend_soft_cap_near_limit" in verdict.reasons
    assert verdict.assessment is not None
    assert verdict.assessment.requested_budget == 900.0
    assert any(check.status == "review" for check in verdict.checks)
