from governance.economic.economic_policy_contract import EconomicPolicyConfig
from governance.economic.economic_policy_engine import EconomicPolicyEngine


class _Decision:
    action = "ads.scale_budget@v1"
    payload = {
        "channel": "ads",
        "economy": {
            "requested_budget": 500.0,
            "expected_incremental_gross_profit": 50.0,
            "expected_incremental_revenue": 1000.0,
            "expected_incremental_roi": 0.1,
        },
    }


class _World:
    economics_state = {
        "cash_on_hand": 5000.0,
        "protected_cash_reserve": 1000.0,
        "available_liquidity": 4500.0,
        "monthly_burn": 1000.0,
        "gross_margin": 0.20,
        "target_margin": 0.25,
        "planned_spend": 1000.0,
        "portfolio_budgets": {"ads": 1000.0},
    }


def test_engine_config_propagates_to_child_policies() -> None:
    engine = EconomicPolicyEngine(
        config=EconomicPolicyConfig(
            tolerated_margin_gap=0.0,
            absolute_floor_margin=0.0,
        )
    )

    verdict = engine.review(_Decision(), _World())

    assert verdict.allowed is False
    assert "margin_veto:below_floor" in verdict.reasons
