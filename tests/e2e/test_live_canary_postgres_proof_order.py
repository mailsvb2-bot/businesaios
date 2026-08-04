from __future__ import annotations

import json
from types import SimpleNamespace

from core.events.log_queries import get_events
from runtime.platform.event_store.postgres_event_store import PostgresEventStore


class FakePostgresPort:
    def __init__(self) -> None:
        self.query = ""
        self.params = ()

    def fetchall(self, query: str, params=()):
        self.query = " ".join(query.split())
        self.params = tuple(params)
        return [
            (
                1,
                "proof-old",
                "tenant-a",
                "system",
                "provider",
                "message_delivered",
                1_000,
                "decision-1",
                "correlation-1",
                json.dumps({"ok": True, "cost": 4.0}),
            ),
            (
                2,
                "proof-new",
                "tenant-a",
                "system",
                "provider",
                "message_delivered",
                900,
                "decision-1",
                "correlation-1",
                json.dumps({"ok": True, "cost": 9.0}),
            ),
        ]


def test_postgres_decision_proofs_use_durable_append_order() -> None:
    port = FakePostgresPort()
    store = PostgresEventStore("postgresql://unused", enabled=True)
    store._port = port
    log = SimpleNamespace(_store=store, tenant_id="tenant-a")

    events = get_events(log, "decision-1", "message_delivered")

    assert [event["event_id"] for event in events] == ["proof-old", "proof-new"]
    assert [event["append_seq"] for event in events] == [1, 2]
    assert "append_seq > %s" in port.query
    assert "ORDER BY append_seq ASC" in port.query
