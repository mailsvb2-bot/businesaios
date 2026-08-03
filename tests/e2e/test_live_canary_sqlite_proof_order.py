from __future__ import annotations

import json
from pathlib import Path

from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


def test_sqlite_decision_proofs_follow_append_sequence_not_rowid(
    tmp_path: Path,
) -> None:
    with SqliteEventStore(str(tmp_path / "proof-order.sqlite3")) as store:
        assert store._db is not None
        rows = (
            (100, 1, "proof-old", 4.0),
            (50, 2, "proof-new", 9.0),
        )
        for rowid, append_seq, event_id, cost in rows:
            store._db.execute(
                """
                INSERT INTO events(
                  rowid, event_id, append_seq, tenant_id, user_id, source,
                  event_type, timestamp_ms, decision_id, correlation_id,
                  payload_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    rowid,
                    event_id,
                    append_seq,
                    "tenant-a",
                    "system",
                    "provider",
                    "message_delivered",
                    1_000,
                    "decision-1",
                    "correlation-1",
                    json.dumps({"ok": True, "cost": cost}),
                ),
            )
        store._db.commit()

        events = store.get_events_for_decision(
            tenant_id="tenant-a",
            decision_id="decision-1",
            event_type="message_delivered",
        )

    assert [event["event_id"] for event in events] == [
        "proof-old",
        "proof-new",
    ]
