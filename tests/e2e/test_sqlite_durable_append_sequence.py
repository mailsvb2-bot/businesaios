from __future__ import annotations

from pathlib import Path

from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


def test_sqlite_cursor_and_tail_use_durable_append_seq_not_rowid(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.sqlite3"
    with SqliteEventStore(str(path)) as store:
        assert store._db is not None
        store._db.execute(
            """
            INSERT INTO events(
                rowid,event_id,append_seq,tenant_id,user_id,source,event_type,
                timestamp_ms,decision_id,correlation_id,payload_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                100,
                "event-5",
                5,
                "tenant-a",
                "user-a",
                "test",
                "decision_issued",
                1_000,
                "decision-5",
                "correlation-5",
                "{}",
            ),
        )
        store._db.execute(
            "UPDATE event_append_sequence SET last_seq=5 WHERE singleton=1"
        )
        store._db.commit()

        rows = list(
            store.iter_events(
                tenant_id="tenant-a",
                after_append_seq=4,
            )
        )

        assert [row["event_id"] for row in rows] == ["event-5"]
        assert rows[0]["append_seq"] == 5
        assert store.latest_append_seq(tenant_id="tenant-a") == 5
