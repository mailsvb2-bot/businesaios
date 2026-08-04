from __future__ import annotations

import json
import sqlite3

from core.experiments.ledger import LiveCanaryLedger
from core.experiments.live_canary_events import EXPERIMENT_ASSIGNMENT
from runtime.platform.event_store import sqlite_read_queries
from runtime.platform.event_store.sqlite_schema import init_schema


class CountingEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.after_append_seq_calls: list[int] = []

    def iter_events(
        self,
        *,
        start_ms=0,
        end_ms=None,
        after_append_seq=0,
        event_types=None,
        **_kwargs,
    ):
        self.after_append_seq_calls.append(int(after_append_seq or 0))
        allowed = set(event_types or ())
        end = int(end_ms) if end_ms is not None else 2**63 - 1
        return iter(
            {**row, "append_seq": append_seq}
            for append_seq, row in enumerate(self.rows, start=1)
            if append_seq > int(after_append_seq or 0)
            and int(row["timestamp_ms"]) >= int(start_ms)
            and int(row["timestamp_ms"]) < end
            and (not allowed or row["event_type"] in allowed)
        )


def assignment(
    decision_id: str,
    timestamp_ms: int,
    *,
    experiment_id: str = "incremental-watchdog",
    candidate_policy_id: str = "candidate@v2",
) -> dict:
    return {
        "tenant_id": "tenant-a",
        "timestamp_ms": timestamp_ms,
        "event_type": EXPERIMENT_ASSIGNMENT,
        "source": "live_canary",
        "decision_id": decision_id,
        "correlation_id": f"correlation-{decision_id}",
        "payload": {
            "experiment_id": experiment_id,
            "candidate_policy_id": candidate_policy_id,
            "tenant_id": "tenant-a",
            "purpose": "live_canary",
            "subject_hash": f"hash-{decision_id}",
            "arm": "candidate",
            "bucket": 1,
            "production_policy_id": "active@v1",
            "action": "send_message@v1",
            "candidate_pct": 1.0,
            "expected_cost": 1.0,
            "eligible": True,
            "reason": "eligible",
            "assigned_at_ms": timestamp_ms,
        },
    }


def ledger_for(events: CountingEvents) -> LiveCanaryLedger:
    return LiveCanaryLedger(
        events,
        experiment_id="incremental-watchdog",
        candidate_policy_id="candidate@v2",
        outcome_window_seconds=60,
    )


def test_materialized_ledger_queries_from_last_append_sequence() -> None:
    events = CountingEvents()
    events.rows.append(assignment("decision-1", 1_001))
    ledger = ledger_for(events)

    first = ledger.metrics(candidate_pct=1.0)
    second = ledger.metrics(candidate_pct=1.0)
    events.rows.append(assignment("decision-2", 1_002))
    third = ledger.metrics(candidate_pct=1.0)

    assert first["candidate_assignments"] == 1
    assert second["candidate_assignments"] == 1
    assert third["candidate_assignments"] == 2
    assert events.after_append_seq_calls == [0, 1, 1]


def test_lower_timestamp_event_is_consumed_immediately_by_append_order() -> None:
    events = CountingEvents()
    events.rows.append(assignment("decision-1", 1_001))
    ledger = ledger_for(events)
    assert ledger.metrics(candidate_pct=1.0)["candidate_assignments"] == 1

    events.rows.append(assignment("decision-late", 900))
    metrics = ledger.metrics(candidate_pct=1.0)

    assert metrics["candidate_assignments"] == 2
    assert events.after_append_seq_calls[-1] == 1
    assert ledger._append_cursor == 2


def test_foreign_canary_tail_advances_shared_append_cursor() -> None:
    events = CountingEvents()
    events.rows.append(assignment("decision-1", 1_001))
    ledger = ledger_for(events)
    ledger.metrics(candidate_pct=1.0)

    events.rows.append(
        assignment(
            "foreign-decision",
            2_000,
            experiment_id="previous-experiment",
            candidate_policy_id="previous-candidate@v1",
        )
    )
    unchanged = ledger.metrics(candidate_pct=1.0)
    ledger.metrics(candidate_pct=1.0)

    assert unchanged["candidate_assignments"] == 1
    assert ledger._append_cursor == 2
    assert events.after_append_seq_calls[-1] == 2


def test_sqlite_rowid_cursor_includes_late_timestamp_append() -> None:
    db = sqlite3.connect(":memory:")
    init_schema(db)
    rows = (
        ("event-1", 1_001),
        ("event-late", 900),
    )
    for event_id, timestamp_ms in rows:
        db.execute(
            """
            INSERT INTO events (
              event_id, tenant_id, user_id, source, event_type, timestamp_ms,
              decision_id, correlation_id, payload_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                "tenant-a",
                "system",
                "live_canary",
                EXPERIMENT_ASSIGNMENT,
                timestamp_ms,
                event_id,
                f"correlation-{event_id}",
                json.dumps({"ok": True}),
            ),
        )
    db.commit()

    events = list(
        sqlite_read_queries.iter_events(
            db,
            tenant_id="tenant-a",
            start_ms=0,
            after_append_seq=1,
            event_types=(EXPERIMENT_ASSIGNMENT,),
        )
    )

    assert [event["event_id"] for event in events] == ["event-late"]
    assert events[0]["append_seq"] == 2
