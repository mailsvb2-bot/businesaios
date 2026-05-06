from governance.economic.economic_policy_engine import EconomicPolicyEngine


class _Decision:
    action = "ads.scale_budget@v1"
    payload = {
        "channel": "ads",
        "economy": {
            "requested_budget": 500.0,
            "expected_incremental_gross_profit": -100.0,
            "expected_incremental_revenue": 100.0,
        },
    }


class _World:
    economics_state = {
        "cash_on_hand": 5000.0,
        "protected_cash_reserve": 1000.0,
        "available_liquidity": 4500.0,
        "monthly_burn": 900.0,
        "gross_margin": 0.35,
        "target_margin": 0.25,
        "planned_spend": 1000.0,
        "portfolio_budgets": {"ads": 1000.0},
    }


def test_negative_roi_is_blocked_even_when_cash_is_available() -> None:
    engine = EconomicPolicyEngine()

    verdict = engine.review(_Decision(), _World())

    assert verdict.allowed is False
    assert verdict.operator_required is False
    assert "stop_loss_veto:negative_roi" in verdict.reasons
    assert verdict.assessment is not None
    assert verdict.assessment.expected_roi < 0.0
    assert verdict.assessment.requested_budget == 500.0
