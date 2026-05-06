from __future__ import annotations

from runtime.platform.event_store.memory_event_store import MemoryEventStore
from core.ads.rl.runtime_state import maturity_gate, bind_runtime_state
from core.governance.evaluators.attribution_maturity import AttributionMaturityGate


def test_maturity_gate_persists_snapshots_in_event_store() -> None:
    es = MemoryEventStore()
    gate = AttributionMaturityGate(maturity_window_ms=1000, event_store=es)

    gate.mark_executed(tenant_id="t1", decision_id="d1", now_ms=1_000)

    reloaded = AttributionMaturityGate(maturity_window_ms=1000, event_store=es)
    assert reloaded.mature_after_ms(tenant_id="t1", decision_id="d1") == 2_000
    assert not reloaded.is_mature(tenant_id="t1", decision_id="d1", now_ms=1_999)
    assert reloaded.is_mature(tenant_id="t1", decision_id="d1", now_ms=2_000)

    events = list(es.iter_events(tenant_id="t1", start_ms=0, end_ms=None, event_type="ads_attribution_maturity_snapshot@v1"))
    assert len(events) == 1
    assert events[0]["decision_id"] == "d1"


def test_runtime_state_binds_maturity_gate_to_event_store() -> None:
    es = MemoryEventStore()
    bind_runtime_state(event_store=es)
    maturity_gate.mark_executed(tenant_id="tenant-a", decision_id="decision-1", now_ms=10)

    fresh = AttributionMaturityGate(maturity_window_ms=24 * 60 * 60 * 1000, event_store=es)
    assert fresh.mature_after_ms(tenant_id="tenant-a", decision_id="decision-1") is not None
