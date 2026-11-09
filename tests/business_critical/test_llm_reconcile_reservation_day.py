from __future__ import annotations
from datetime import datetime, timezone
from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
from core.telemetry.event_types import LLM_COMPLETED
class _Store:
    def __init__(self) -> None:
        self.state = {"pending": {"request-1": {"user_id": "user-1", "tokens": 10}}}
        self.windows: list[tuple[int, int]] = []
    def iter_events(self, *, tenant_id, start_ms, end_ms, event_type):
        assert (tenant_id, event_type) == ("tenant-1", LLM_COMPLETED)
        self.windows.append((start_ms, end_ms))
        completed_at = int(datetime(2026, 11, 8, 23, 59, tzinfo=timezone.utc).timestamp() * 1000)
        if start_ms <= completed_at < end_ms:
            yield {"user_id": "user-1", "payload": {"request_id": "request-1", "total_tokens": 10}}

    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        assert (tenant_id, key) == ("tenant-1", "llm:pending:v1:2026-11-08")
        if self.state != expected:
            return False
        self.state = value
        return True


def test_reconcile_uses_reservation_day_not_current_day():
    store = _Store()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    assert budget._reconcile_completed(tenant_id="tenant-1", day="2026-11-08", current=store.state)
    expected_start = int(datetime(2026, 11, 8, tzinfo=timezone.utc).timestamp() * 1000)
    assert (store.state, store.windows) == ({"pending": {}}, [(expected_start, expected_start + 86_400_000)])


def test_reconcile_rejects_invalid_day_without_releasing_claim():
    store = _Store()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    assert not budget._reconcile_completed(tenant_id="tenant-1", day="2026-11-08-invalid", current=store.state)
    assert (store.state["pending"]["request-1"]["tokens"], store.windows) == (10, [])
