from unittest.mock import Mock
import pytest
from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
def corrupt_store():
    store = Mock(sum_event_payload_int=None)
    store.iter_events.return_value = [{"user_id": "u", "payload": {"request_id": "req", "total_tokens": "not-a-number"}}]
    store.get_setting.return_value = {"pending": {"req": {"user_id": "u", "tokens": 10}}}; return store
def test_corrupt_completion_never_reclaims_reservation():
    budget = EventStoreDailyTokenBudget(event_store=(store := corrupt_store()), caps=BudgetCaps())
    assert budget._reconcile_completed(tenant_id="t", day=budget._day(), current=store.get_setting()) is False and not store.compare_and_set_setting.called
def test_corrupt_completion_fallback_aggregator_fails_closed():
    with pytest.raises(RuntimeError, match="LLM_BUDGET_CORRUPT_COMPLETION"): EventStoreDailyTokenBudget(event_store=corrupt_store(), caps=BudgetCaps()).can_spend(tenant_id="t", user_id="u", tokens=1)
