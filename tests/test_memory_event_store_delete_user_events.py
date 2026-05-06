from __future__ import annotations

from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_delete_user_events_respects_tenant_scope() -> None:
    store = MemoryEventStore()
    store.append_event({"tenant_id": "t1", "user_id": "u1", "event_type": "a", "timestamp_ms": 1})
    store.append_event({"tenant_id": "t1", "user_id": "u2", "event_type": "b", "timestamp_ms": 2})
    store.append_event({"tenant_id": "t2", "user_id": "u1", "event_type": "c", "timestamp_ms": 3})

    deleted = store.delete_user_events(tenant_id="t1", user_id="u1")

    assert deleted == 1
    assert list(store.iter_events(tenant_id="t1")) == [{"tenant_id": "t1", "user_id": "u2", "event_type": "b", "timestamp_ms": 2}]
    assert list(store.iter_events(tenant_id="t2")) == [{"tenant_id": "t2", "user_id": "u1", "event_type": "c", "timestamp_ms": 3}]
