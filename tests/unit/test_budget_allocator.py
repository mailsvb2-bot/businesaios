from growth.ads.budget_allocator import BudgetAllocator


def test_budget_allocator_returns_payload():
    allocator = BudgetAllocator()
    result = allocator.allocate({'amount': 100})
    assert result['kind'] == 'budget_allocation'
