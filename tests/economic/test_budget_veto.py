from governance.economic.economic_policy_engine import EconomicPolicyEngine


class _Decision:
    action = "ads.scale_budget@v1"
    payload = {
        "channel": "ads",
        "economy": {
            "requested_budget": 1200.0,
            "expected_incremental_gross_profit": 600.0,
            "expected_incremental_revenue": 2000.0,
            "expected_incremental_roi": 0.5,
        },
    }


class _World:
    economics_state = {
        "cash_on_hand": 5000.0,
        "protected_cash_reserve": 1000.0,
        "available_liquidity": 4000.0,
        "monthly_burn": 1000.0,
        "gross_margin": 0.35,
        "target_margin": 0.30,
        "planned_spend": 3000.0,
        "hard_spend_cap": 0.0,
        "portfolio_budgets": {"ads": 1000.0},
    }


def test_budget_veto_when_request_exceeds_channel_cap() -> None:
    engine = EconomicPolicyEngine()

    verdict = engine.review(_Decision(), _World())

    assert verdict.allowed is False
    assert verdict.operator_required is False
    assert verdict.reason == "budget_veto:spend_cap_exceeded"
    assert "budget_veto:spend_cap_exceeded" in verdict.reasons
    assert verdict.metadata["intent_channel"] == "ads"
    assert verdict.assessment is not None
    assert verdict.assessment.requested_budget == 1200.0
