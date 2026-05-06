from __future__ import annotations

from runtime.platform.event_store.memory_event_store import MemoryEventStore
from core.ads.rl.policy_store import PolicyStore
from core.ads.rl.runtime_state import policy_store, bind_runtime_state


def test_policy_store_persists_snapshots_in_event_store() -> None:
    es = MemoryEventStore()
    store = PolicyStore(event_store=es)

    first = store.put(tenant_id="t1", policy_id="ads.rl.policy.v1", params={"budget_multiplier_x1000": 1050})
    second = store.put(tenant_id="t1", policy_id="ads.rl.policy.v1", params={"budget_multiplier_x1000": 950})

    assert first.version == 1
    assert second.version == 2

    latest = PolicyStore(event_store=es).get_latest(tenant_id="t1")
    assert latest is not None
    assert latest.version == 2
    assert latest.params["budget_multiplier_x1000"] == 950

    events = list(es.iter_events(tenant_id="t1", start_ms=0, end_ms=None, event_type="ads_rl_policy_snapshot@v1"))
    assert len(events) == 2


def test_runtime_state_reads_bound_event_store() -> None:
    es = MemoryEventStore()
    bind_runtime_state(event_store=es)
    policy_store.put(tenant_id="tenant-a", policy_id="ads.rl.policy.v1", params={"budget_multiplier_x1000": 1100})

    latest = policy_store.get_latest(tenant_id="tenant-a")

    assert latest is not None
    assert latest.version == 1
    assert latest.params["budget_multiplier_x1000"] == 1100
