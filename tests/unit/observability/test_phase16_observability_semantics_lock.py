from __future__ import annotations

from observability.platform.telemetry.event_sink import EventStoreSink
from observability.platform.telemetry.event_stream import InMemoryEventStore
from observability.platform.telemetry.metrics import Metrics
from runtime.observability.metrics import Metrics as RuntimeMetrics


def test_platform_event_store_sink_semantics_preserved() -> None:
    store = InMemoryEventStore()
    sink = EventStoreSink(store=store)

    sink.emit(tenant_id="t1", user_id="u1", event_type="decision.made", payload={"ok": True})

    events = list(store.latest_events(tenant_id="t1", event_type="decision.made"))
    assert len(events) == 1
    event = events[0]
    assert event["tenant_id"] == "t1"
    assert event["user_id"] == "u1"
    assert event["event_type"] == "decision.made"
    assert event["payload"] == {"ok": True}
    assert "ts_iso" in event

def test_metrics_surfaces_preserve_observability_semantics() -> None:
    class _Store:
        def __init__(self) -> None:
            self.calls = []

        def append(self, **kwargs):
            self.calls.append(kwargs)

    store = _Store()
    metrics = Metrics(store=store)
    metrics.incr(tenant_id="t1", name="hits", value=2, tags={"channel": "email"})
    metrics.gauge(tenant_id="t1", name="latency_ms", value=12.5)

    assert store.calls == [
        {
            "tenant_id": "t1",
            "user_id": None,
            "event_type": "metric_incr",
            "payload": {"name": "hits", "value": 2, "tags": {"channel": "email"}},
        },
        {
            "tenant_id": "t1",
            "user_id": None,
            "event_type": "metric_gauge",
            "payload": {"name": "latency_ms", "value": 12.5, "tags": {}},
        },
    ]

    runtime_metrics = RuntimeMetrics()
    runtime_metrics.set("latency_ms", 12)
    assert runtime_metrics.get("latency_ms") == 12.0
    assert runtime_metrics.snapshot() == {"latency_ms": 12.0}
