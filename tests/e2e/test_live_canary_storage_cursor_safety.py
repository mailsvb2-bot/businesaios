from __future__ import annotations

import time
from pathlib import Path

from core.events.log import EventLog
from core.experiments.live_canary_events import EXPERIMENT_ASSIGNMENT
from core.experiments.repositories.live_canary_assignment_safety import (
    LiveCanaryAssignmentSafety,
)
from runtime.platform.event_store.postgres_event_store import PostgresEventStore
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


def event(
    event_id: str,
    *,
    decision_id: str,
    timestamp_ms: int,
    tenant_id: str = "tenant-a",
) -> dict:
    return {
        "event_id": event_id,
        "tenant_id": tenant_id,
        "user_id": "system",
        "source": "live_canary",
        "event_type": EXPERIMENT_ASSIGNMENT,
        "timestamp_ms": timestamp_ms,
        "decision_id": decision_id,
        "correlation_id": f"correlation-{decision_id}",
        "payload": {
            "experiment_id": "storage-cursor",
            "candidate_policy_id": "candidate@v2",
            "tenant_id": tenant_id,
            "purpose": "live_canary",
            "subject_hash": f"hash-{decision_id}",
            "arm": "candidate",
            "candidate_pct": 1.0,
            "expected_cost": 1.0,
            "eligible": True,
            "assigned_at_ms": timestamp_ms,
        },
    }


def test_sqlite_retention_cannot_reuse_consumed_append_cursor(tmp_path: Path) -> None:
    path = tmp_path / "events.sqlite3"
    with SqliteEventStore(str(path)) as store:
        store.append_event(
            event("event-1", decision_id="decision-1", timestamp_ms=1_001)
        )
        first = list(
            store.iter_events(
                tenant_id="tenant-a",
                after_append_seq=0,
                event_types=(EXPERIMENT_ASSIGNMENT,),
            )
        )[0]
        first_cursor = int(first["append_seq"])
        assert store._db is not None
        store._db.execute("DELETE FROM events WHERE event_id=?", ("event-1",))
        store._db.commit()

        store.append_event(
            event("event-2", decision_id="decision-2", timestamp_ms=900)
        )
        later = list(
            store.iter_events(
                tenant_id="tenant-a",
                after_append_seq=first_cursor,
                event_types=(EXPERIMENT_ASSIGNMENT,),
            )
        )

        assert [row["event_id"] for row in later] == ["event-2"]
        assert int(later[0]["append_seq"]) > first_cursor


class FakePostgresPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple | None]] = []
        self.commits = 0

    def execute(self, sql: str, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def commit(self):
        self.commits += 1


def test_postgres_serializes_sequence_allocation_until_commit() -> None:
    port = FakePostgresPort()
    store = PostgresEventStore("postgresql://unused", enabled=True)
    store._port = port

    store.append_event(
        event("event-pg", decision_id="decision-pg", timestamp_ms=1_001)
    )

    assert "pg_advisory_xact_lock" in port.calls[0][0]
    assert "INSERT INTO events" in port.calls[1][0]
    assert port.commits == 1


def test_shared_assignment_safety_consumes_late_timestamp_by_append_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "shared.sqlite3"
    with SqliteEventStore(str(path)) as store:
        log = EventLog(store, tenant="tenant-a")
        safety = LiveCanaryAssignmentSafety(
            log,
            experiment_id="storage-cursor",
            candidate_policy_id="candidate@v2",
        )
        store.append_event(
            event("event-a", decision_id="decision-a", timestamp_ms=1_001)
        )
        assert safety.metrics(candidate_pct=1.0)["candidate_actions_24h"] == 1

        store.append_event(
            event("event-b", decision_id="decision-b", timestamp_ms=900)
        )
        metrics = safety.metrics(candidate_pct=1.0)

        assert metrics["candidate_actions_24h"] == 2
        assert safety._append_cursor == store.latest_append_seq(tenant_id="tenant-a")


def test_event_log_decision_lookup_uses_indexed_sqlite_query(tmp_path: Path) -> None:
    path = tmp_path / "proofs.sqlite3"
    with SqliteEventStore(str(path)) as store:
        now_ms = int(time.time() * 1000)
        for index in range(20):
            store.append_event(
                event(
                    f"noise-{index}",
                    decision_id=f"noise-decision-{index}",
                    timestamp_ms=now_ms + index,
                )
            )
        store.append_event(
            event(
                "target-event",
                decision_id="target-decision",
                timestamp_ms=now_ms + 100,
            )
        )
        statements: list[str] = []
        assert store._db is not None
        store._db.set_trace_callback(statements.append)
        rows = EventLog(store, tenant="tenant-a").get_events(
            "target-decision",
            EXPERIMENT_ASSIGNMENT,
        )

        assert [row["event_id"] for row in rows] == ["target-event"]
        select_sql = next(
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
        )
        assert "decision_id=" in select_sql
        assert "event_type=" in select_sql
