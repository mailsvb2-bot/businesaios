from __future__ import annotations

from core.ads.rl.policy_store import PolicyStore
from core.governance.evaluators.attribution_maturity import AttributionMaturityGate
from core.governance.guards.policy_update_gate import PolicyUpdateGate
from core.governance.readers.event_sourced_path import (
    assert_governance_event_store_contract,
    inspect_governance_event_path,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_governance_event_sourced_path_is_reconstructable() -> None:
    store = MemoryEventStore()
    PolicyUpdateGate(event_store=store).propose(tenant_id="t1", domain="pricing", update_id="u1", payload={"price": 1}, now_ms=1000)
    AttributionMaturityGate(event_store=store, maturity_window_ms=100).mark_executed(tenant_id="t1", decision_id="d1", now_ms=1200)
    PolicyStore(event_store=store).put(tenant_id="t1", policy_id="ads.rl.policy.v1", params={"weights": [1, 2, 3]})

    status = inspect_governance_event_path(event_store=store, tenant_id="t1")
    assert status.ok is True
    assert status.policy_gate_events >= 1
    assert status.attribution_events >= 1
    assert status.rl_policy_events >= 1


def test_governance_event_store_contract_missing_methods() -> None:
    class BrokenStore:
        pass

    try:
        assert_governance_event_store_contract(BrokenStore())
    except RuntimeError as exc:
        assert "GOVERNANCE_EVENT_STORE_CONTRACT_MISSING" in str(exc)
    else:
        raise AssertionError("expected contract error")
