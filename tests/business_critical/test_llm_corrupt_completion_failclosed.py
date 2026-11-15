from unittest.mock import Mock

import pytest

from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget


def corrupt_store():
    store = Mock(sum_event_payload_int=None)
    store.iter_events.return_value = [
        {"user_id": "u", "payload": {"request_id": "req", "total_tokens": "not-a-number"}}
    ]
    store.get_setting.return_value = {"pending": {"req": {"user_id": "u", "tokens": 10}}}
    return store


def test_corrupt_completion_never_reclaims_reservation():
    budget = EventStoreDailyTokenBudget(event_store=(store := corrupt_store()), caps=BudgetCaps())
    assert (
        budget._reconcile_completed(tenant_id="t", day=budget._day(), current=store.get_setting()) is False
        and not store.compare_and_set_setting.called
    )


def test_corrupt_completion_fallback_aggregator_fails_closed():
    with pytest.raises(RuntimeError, match="LLM_BUDGET_CORRUPT_COMPLETION"):
        EventStoreDailyTokenBudget(event_store=corrupt_store(), caps=BudgetCaps()).can_spend(
            tenant_id="t", user_id="u", tokens=1
        )


@pytest.mark.parametrize("value", ["not-a-number", "10", True, 0, -1, None])
def test_fast_aggregate_cannot_hide_corrupt_provider_completion(value):
    store = Mock()
    store.sum_event_payload_int.return_value = 0
    store.iter_events.return_value = [{"user_id": "u", "payload": {"request_id": "req", "total_tokens": value}}]
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    with pytest.raises(RuntimeError, match="LLM_BUDGET_CORRUPT_COMPLETION"):
        budget.can_spend(tenant_id="t", user_id="u", tokens=1)
    store.sum_event_payload_int.assert_not_called()


def test_fast_aggregate_cannot_underreport_valid_provider_completion():
    store = Mock()
    store.sum_event_payload_int.return_value = 0
    store.iter_events.return_value = [{"user_id": "u", "payload": {"request_id": "req", "total_tokens": 20}}]
    budget = EventStoreDailyTokenBudget(
        event_store=store,
        caps=BudgetCaps(tenant_tokens_per_day=20, user_tokens_per_day=20),
    )
    assert budget.can_spend(tenant_id="t", user_id="u", tokens=1) is False
    store.sum_event_payload_int.assert_not_called()


def test_completion_without_user_identity_fails_closed():
    store = Mock()
    store.iter_events.return_value = [{"user_id": "", "payload": {"request_id": "req", "total_tokens": 20}}]
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    with pytest.raises(RuntimeError, match="LLM_BUDGET_CORRUPT_COMPLETION"):
        budget.can_spend(tenant_id="t", user_id="u", tokens=1)


@pytest.mark.parametrize(
    "row",
    [
        {"user_id": "u", "tokens": "10"},
        {"user_id": "u", "tokens": True},
        {"user_id": "u", "tokens": 0},
        {"user_id": "u", "tokens": -10},
        {"user_id": "", "tokens": 10},
        {"tokens": 10},
        None,
    ],
)
def test_corrupt_pending_reservation_cannot_release_budget_headroom(row):
    store = Mock()
    store.get_setting.return_value = {"pending": {"stale": row}}
    store.iter_events.return_value = []
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    assert budget.reserve(tenant_id="t", user_id="u", tokens=1, request_id="new") is None
    store.compare_and_set_setting.assert_not_called()
