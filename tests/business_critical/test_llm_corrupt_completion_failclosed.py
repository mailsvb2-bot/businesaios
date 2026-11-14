"""Regression: corrupt provider completions must never free or undercount LLM budget."""
import pytest

from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget


class CorruptStore:
    def __init__(self):
        self.cas_calls = 0

    def iter_events(self, **kwargs):
        return [{"user_id": "u", "payload": {"request_id": "req", "total_tokens": "not-a-number"}}]

    def get_setting(self, **kwargs):
        return {"pending": {"req": {"user_id": "u", "tokens": 10}}}

    def compare_and_set_setting(self, **kwargs):
        self.cas_calls += 1
        return True


def test_corrupt_completion_never_reclaims_reservation():
    store = CorruptStore()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    assert budget._reconcile_completed(tenant_id="t", day=budget._day(), current=store.get_setting()) is False
    assert store.cas_calls == 0


def test_corrupt_completion_fallback_aggregator_fails_closed():
    store = CorruptStore()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    with pytest.raises(RuntimeError, match="LLM_BUDGET_CORRUPT_COMPLETION"):
        budget.can_spend(tenant_id="t", user_id="u", tokens=1)
