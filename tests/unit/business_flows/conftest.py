from __future__ import annotations

from types import SimpleNamespace

import pytest


class FlowStore:
    """Event Store double: send_message tracking appends the tracked event."""

    def __init__(self):
        self.events: list[dict] = []

    def iter_events(self, *, tenant_id, start_ms=0, end_ms=None, user_id=None, event_type=None, **_):
        return [
            e
            for e in self.events
            if e["tenant_id"] == tenant_id
            and (user_id is None or e["user_id"] == user_id)
            and (event_type is None or e["event_type"] == event_type)
        ]

    def delete_user_events(self, *, tenant_id, user_id):
        before = len(self.events)
        self.events = [e for e in self.events if not (e["tenant_id"] == tenant_id and e["user_id"] == user_id)]
        return before - len(self.events)


class FlowEffects:
    def __init__(self, store: FlowStore):
        self.store, self.sent = store, []

    def send_message(self, **kw):
        self.sent.append(kw)
        if kw.get("track_event_type"):
            self.store.events.append(
                {
                    "tenant_id": kw["tenant_id"],
                    "user_id": kw["user_id"],
                    "event_type": kw["track_event_type"],
                    "timestamp_ms": len(self.store.events),
                    "payload": dict(kw["track_payload"]),
                }
            )
        return {"ok": True, "router_evidence": {"source": "telegram", "message_id": len(self.sent)}}


@pytest.fixture
def flow():
    store = FlowStore()
    effects = FlowEffects(store)
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d", correlation_id="c"))

    def run(handler, **payload):
        out = handler({"tenant_id": "t1", "user_id": "u1", **payload}, effects, env, event_store=store)
        return out, effects.sent[-1]["text"]

    return SimpleNamespace(store=store, effects=effects, run=run)
