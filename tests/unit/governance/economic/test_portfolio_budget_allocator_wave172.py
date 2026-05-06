from governance.economic.action_economics_model import ActionEconomicsIntent, ActionEconomicsSnapshot
from governance.economic.portfolio_budget_allocator import PortfolioBudgetAllocator


def test_allocator_tolerates_non_numeric_explicit_budget_values():
    allocator = PortfolioBudgetAllocator()
    snapshot = ActionEconomicsSnapshot(
        planned_spend=100.0,
        portfolio_budgets={"ads": "bad", "email": 20},
    )
    intent = ActionEconomicsIntent(action_type="allocate_budget", channel="ads")
    assert allocator.allocate(snapshot=snapshot, intent=intent) == {"email": 20.0}
