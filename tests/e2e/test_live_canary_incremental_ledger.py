from __future__ import annotations

from core.experiments.ledger import LiveCanaryLedger
from core.experiments.live_canary_events import EXPERIMENT_ASSIGNMENT


class CountingEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.start_ms_calls: list[int] = []

    def iter_events(
        self,
        *,
        start_ms=0,
        end_ms=None,
        event_types=None,
        **_kwargs,
    ):
        self.start_ms_calls.append(int(start_ms))
        allowed = set(event_types or ())
        end = int(end_ms) if end_ms is not None else 2**63 - 1
        return iter(
            row
            for row in self.rows
            if int(row["timestamp_ms"]) >= int(start_ms)
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


def test_materialized_ledger_only_queries_from_last_event_cursor() -> None:
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
    assert events.start_ms_calls == [0, 1_001, 1_001]


def test_periodic_reconciliation_recovers_late_lower_timestamp_event() -> None:
    events = CountingEvents()
    events.rows.append(assignment("decision-1", 1_001))
    ledger = ledger_for(events)
    assert ledger.metrics(candidate_pct=1.0)["candidate_assignments"] == 1

    events.rows.append(assignment("decision-late", 900))
    ledger._last_reconcile_monotonic -= 60 * 60 + 1
    metrics = ledger.metrics(candidate_pct=1.0)

    assert metrics["candidate_assignments"] == 2
    assert events.start_ms_calls[-1] == 0


def test_foreign_canary_tail_advances_shared_scan_cursor() -> None:
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
    assert ledger._evidence_cursor_ms == 2_000
    assert events.start_ms_calls[-1] == 2_000
