"""Regression: corrupt provider completions must never free or undercount LLM budget."""
from unittest.mock import Mock

import pytest
from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget


def corrupt_store():
    store = Mock()
    store.iter_events.return_value = [{"user_id": "u", "payload": {"request_id": "req", "total_tokens": "not-a-number"}}]
    store.get_setting.return_value = {"pending": {"req": {"user_id": "u", "tokens": 10}}}
    return store


def test_corrupt_completion_never_reclaims_reservation():
    store = corrupt_store()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    assert budget._reconcile_completed(tenant_id="t", day=budget._day(), current=store.get_setting()) is False
    store.compare_and_set_setting.assert_not_called()


def test_corrupt_completion_fallback_aggregator_fails_closed():
    store = corrupt_store()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    with pytest.raises(RuntimeError, match="LLM_BUDGET_CORRUPT_COMPLETION"):
        budget.can_spend(tenant_id="t", user_id="u", tokens=1)
