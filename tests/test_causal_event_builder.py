from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from core.causal.builders.event_store_builder import EventCausalBuilder


class FakeEventStore:
    def __init__(self, events: list[dict[str, Any]]):
        self._events = list(events)

    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms: int, event_type: str) -> Iterable[Mapping[str, Any]]:
        for e in self._events:
            if str(e.get("tenant_id")) != str(tenant_id):
                continue
            if str(e.get("event_type")) != str(event_type):
                continue
            ts = int(e.get("timestamp_ms") or 0)
            if ts < int(start_ms) or ts > int(end_ms):
                continue
            yield e


def test_build_binary_dataset():
    evs = [
        {"tenant_id": "t1", "event_type": "ads_plan_applied", "timestamp_ms": 10, "user_id": "u1", "payload": {"platform": "meta"}},
        {"tenant_id": "t1", "event_type": "payment_captured", "timestamp_ms": 20, "user_id": "u1", "payload": {"amount": 100}},
        {"tenant_id": "t1", "event_type": "payment_captured", "timestamp_ms": 21, "user_id": "u2", "payload": {"amount": 50}},
    ]
    es = FakeEventStore(evs)
    b = EventCausalBuilder(unit_id_key="user_id")
    ds = b.build_binary_treatment_dataset(
        es,
        tenant_id="t1",
        treatment_event="ads_plan_applied",
        outcome_event="payment_captured",
        outcome_value_path=("payload", "amount"),
        covariate_extractors=(("platform", ("payload", "platform")),),
        start_ms=1,
        end_ms=100,
    )
    # u1 treated, u2 control
    assert len(ds.rows) == 2
    m = {r.unit_id: r for r in ds.rows}
    assert m["u1"].treatment == 1.0
    assert m["u2"].treatment == 0.0
    assert m["u1"].outcome == 100.0
    assert m["u2"].outcome == 50.0
