"""Exercise canonical reservation/release against a real compare-and-set contract."""
from copy import deepcopy
import pytest
from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget

class _AtomicStore:
    def __init__(self):
        self.state = {}
    def get_setting(self, *, tenant_id, key):
        return deepcopy(self.state.get((tenant_id, key)))
    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        if self.state.get((tenant_id, key)) != expected:
            return False
        self.state[(tenant_id, key)] = deepcopy(value)
        return True
    def iter_events(self, **kwargs):
        return iter(())

def test_actual_reserve_release_cas_rejects_stale_pre_aba_snapshot():
    store = _AtomicStore()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    key = "llm:pending:v2"
    store.state[("tenant", key)] = {"pending": {}}
    stale = store.get_setting(tenant_id="tenant", key=key)
    day = budget.reserve(tenant_id="tenant", user_id="user", tokens=1, request_id="one")
    assert day is not None
    assert budget.release(tenant_id="tenant", request_id="one", day=day)
    current = store.get_setting(tenant_id="tenant", key=key)
    assert current["pending"] == stale["pending"] and current["revision"] == 2
    assert not store.compare_and_set_setting(tenant_id="tenant", key=key, expected=stale, value={"pending": {"rogue": {}}})
    assert budget.reserve(tenant_id="tenant", user_id="user", tokens=1, request_id="two") == day

def test_revision_legacy_compatibility_and_fail_closed():
    next_state = EventStoreDailyTokenBudget._next_v2_state
    assert next_state(None, {}) == {"revision": 1, "pending": {}}
    assert next_state({"pending": {}}, {}) == {"revision": 1, "pending": {}}
    for invalid in (-1, True, "3", 1.5, None):
        with pytest.raises(ValueError, match="LLM_BUDGET_CORRUPT_REVISION"):
            next_state({"revision": invalid, "pending": {}}, {})
