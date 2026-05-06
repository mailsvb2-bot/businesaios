from __future__ import annotations

from runtime.boot.boot_observability import emit_boot_completed
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_boot_completed_is_emitted_to_event_stream() -> None:
    store = MemoryEventStore()
    emit_boot_completed(
        event_store=store,
        tenant_id="t1",
        run_mode="test",
        env="test",
        components={"event_store": True, "decision_core": True},
    )
    rows = list(store.iter_events(tenant_id="t1", start_ms=0, end_ms=None, event_type="runtime_boot_completed"))
    assert rows
    assert rows[-1]["payload"]["components"]["decision_core"] is True
