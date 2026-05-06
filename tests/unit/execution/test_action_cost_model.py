from execution.action_budget_engine import ActionBudgetCost, ActionBudgetDecision, ActionBudgetSnapshot
from execution.action_cost_model import ActionCostModel


def test_action_cost_model_prefers_budget_decision_when_available() -> None:
    model = ActionCostModel()
    budget_decision = ActionBudgetDecision(
        allowed=True,
        reason="ok",
        cost=ActionBudgetCost(
            estimated_cost=12.5,
            currency="USD",
            outbound_count=2,
            publication_count=1,
            irreversible_count=0,
            budget_change_amount=100.0,
            reasoning=("explicit_cost",),
        ),
        snapshot_before=ActionBudgetSnapshot(currency="USD"),
        snapshot_after=ActionBudgetSnapshot(currency="USD"),
    )

    result = model.from_sources(
        action_type="send_outreach_email",
        payload={"requested_budget": 100.0, "economy": {"channel": "email"}},
        budget_decision=budget_decision,
    )
    assert result.estimated_cost == 12.5
    assert result.budget_change_amount == 100.0
    assert result.outbound_count == 2
    assert result.metadata["source"] == "budget_decision"
