from types import SimpleNamespace

from execution.budget_guard import BudgetGuard


class _Request(SimpleNamespace):
    pass


def test_budget_guard_honors_prefixed_operational_constraints() -> None:
    guard = BudgetGuard()
    request = _Request(
        channel="headless",
        economy={"currency": "USD", "max_run_cost": 1_000.0},
        constraints={
            "operational_budget_max_actions_per_hour": 1,
            "operational_budget_max_actions_per_day": 10,
            "operational_budget_max_outbound_per_window": 10,
            "operational_budget_max_new_assets_per_day": 10,
            "operational_budget_max_irreversible_actions_per_window": 10,
        },
        meta={},
    )
    payload = {
        "persistent_counters": {
            "actions_hour": 1,
            "actions_day": 1,
        },
        "economy": {
            "requested_budget": 10.0,
            "expected_incremental_revenue": 100.0,
            "expected_incremental_gross_profit": 20.0,
            "expected_incremental_roi": 2.0,
        },
    }
    world_state = {
        "economics_state": {
            "currency": "USD",
            "cash_on_hand": 10_000.0,
            "available_liquidity": 10_000.0,
            "monthly_burn": 500.0,
            "gross_margin": 0.4,
            "planned_spend": 200.0,
            "hard_spend_cap": 500.0,
        }
    }

    decision = guard.evaluate(request=request, action_type="write_email", payload=payload, world_state=world_state)

    assert decision.allowed is False
    assert decision.reason == "operational_budget_exceeded"
    assert "operational_budget:max_actions_per_hour" in decision.reasons
    assert decision.metadata["owners"]["operational_budget"] == "execution.operational_budget"
