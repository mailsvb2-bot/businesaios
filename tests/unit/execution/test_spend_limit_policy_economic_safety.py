from types import SimpleNamespace

from execution.spend_limit_policy import SpendLimitPolicy


class _Request(SimpleNamespace):
    pass


def test_spend_limit_policy_emits_soft_cap_review() -> None:
    policy = SpendLimitPolicy()
    request = _Request(
        channel="ads",
        economy={"currency": "USD", "max_run_cost": 500.0},
        constraints={},
    )
    world_state = {
        "economics_state": {
            "currency": "USD",
            "cash_on_hand": 10_000.0,
            "available_liquidity": 10_000.0,
            "monthly_burn": 1_000.0,
            "gross_margin": 0.4,
            "planned_spend": 100.0,
            "hard_spend_cap": 500.0,
            "expected_incremental_revenue": 300.0,
            "expected_incremental_gross_profit": 120.0,
            "expected_incremental_roi": 1.2,
        }
    }
    payload = {
        "channel": "ads",
        "requested_budget": 90.0,
        "economy": {
            "requested_budget": 90.0,
            "expected_incremental_revenue": 300.0,
            "expected_incremental_gross_profit": 120.0,
            "expected_incremental_roi": 1.2,
        },
    }

    decision = policy.evaluate(request=request, action_type="launch_campaign", payload=payload, world_state=world_state)

    assert decision.allowed is True
    assert decision.operator_required is True
    assert decision.spend_cap_check["status"] == "review"


def test_spend_limit_policy_blocks_hard_cap_veto() -> None:
    policy = SpendLimitPolicy()
    request = _Request(
        channel="ads",
        economy={"currency": "USD", "max_run_cost": 500.0},
        constraints={},
    )
    world_state = {
        "economics_state": {
            "currency": "USD",
            "cash_on_hand": 10_000.0,
            "available_liquidity": 10_000.0,
            "monthly_burn": 1_000.0,
            "gross_margin": 0.4,
            "planned_spend": 100.0,
            "hard_spend_cap": 80.0,
            "expected_incremental_revenue": 300.0,
            "expected_incremental_gross_profit": 120.0,
            "expected_incremental_roi": 1.2,
        }
    }
    payload = {
        "channel": "ads",
        "requested_budget": 120.0,
        "economy": {
            "requested_budget": 120.0,
            "expected_incremental_revenue": 300.0,
            "expected_incremental_gross_profit": 120.0,
            "expected_incremental_roi": 1.2,
        },
    }

    decision = policy.evaluate(request=request, action_type="launch_campaign", payload=payload, world_state=world_state)

    assert decision.allowed is False
    assert decision.operator_required is False
    assert decision.spend_cap_check["status"] == "veto"
