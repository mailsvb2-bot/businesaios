from __future__ import annotations

import pytest

from core.events.log import EventLog
from core.events.log_queries import get_events
from core.experiments.guardrails import CanaryDecision, GuardrailResult
from core.experiments.ledger import LiveCanaryLedger
from core.experiments.live_canary_events import EXPERIMENT_ASSIGNMENT
from runtime.experiments.watchdog import LiveCanaryWatchdog
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _event(
    event_id: str,
    *,
    event_type: str,
    decision_id: str,
    user_id: str = "system",
    payload: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "tenant_id": "tenant-a",
        "user_id": user_id,
        "source": "test",
        "event_type": event_type,
        "timestamp_ms": 1_000,
        "decision_id": decision_id,
        "correlation_id": f"correlation-{decision_id}",
        "payload": dict(payload or {}),
    }


def test_watchdog_keeps_polling_after_successful_rollback() -> None:
    watchdog = LiveCanaryWatchdog.__new__(LiveCanaryWatchdog)
    watchdog.interval_seconds = 1.0
    observed: list[CanaryDecision] = []
    results = iter(
        (
            GuardrailResult(CanaryDecision.ROLLBACK, ("breach",), {}),
            GuardrailResult(CanaryDecision.CONTINUE, ("healthy",), {}),
        )
    )

    def run_once() -> GuardrailResult:
        result = next(results)
        observed.append(result.decision)
        return result

    class StopAfterTwoPulses:
        def __init__(self) -> None:
            self.pulses = 0

        def is_set(self) -> bool:
            return self.pulses >= 2

        def wait(self, _seconds: float) -> None:
            self.pulses += 1

    watchdog.run_once = run_once
    last = watchdog.run_forever(StopAfterTwoPulses())

    assert observed == [CanaryDecision.ROLLBACK, CanaryDecision.CONTINUE]
    assert last is CanaryDecision.CONTINUE


def test_watchdog_retries_after_transient_rollback_submission_failure() -> None:
    watchdog = LiveCanaryWatchdog.__new__(LiveCanaryWatchdog)
    watchdog.interval_seconds = 1.0
    attempts = 0

    class Coordinator:
        _rollback_required = False

    watchdog.coordinator = Coordinator()

    def run_once() -> GuardrailResult:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("runtime executor temporarily unavailable")
        return GuardrailResult(CanaryDecision.CONTINUE, ("healthy",), {})

    class StopAfterTwoPulses:
        def __init__(self) -> None:
            self.pulses = 0

        def is_set(self) -> bool:
            return self.pulses >= 2

        def wait(self, _seconds: float) -> None:
            self.pulses += 1

    watchdog.run_once = run_once
    last = watchdog.run_forever(StopAfterTwoPulses())

    assert attempts == 2
    assert watchdog.coordinator._rollback_required is True
    assert last is CanaryDecision.CONTINUE


def test_decision_lookup_outage_is_not_converted_to_missing_evidence() -> None:
    class BrokenStore:
        def get_events_for_decision(self, **_kwargs):
            raise OSError("indexed lookup unavailable")

        def iter_events(self, **_kwargs):
            raise OSError("fallback scan unavailable")

    class BrokenLog:
        tenant_id = "tenant-a"
        _store = BrokenStore()

    with pytest.raises(RuntimeError, match="EVENT_DECISION_LOOKUP_UNAVAILABLE"):
        get_events(BrokenLog(), "decision-1", EXPERIMENT_ASSIGNMENT)


def test_materialized_ledger_advances_over_ordinary_tenant_tail() -> None:
    store = MemoryEventStore()
    store.append_event(
        _event(
            "assignment-1",
            event_type=EXPERIMENT_ASSIGNMENT,
            decision_id="decision-1",
            payload={
                "experiment_id": "tail-canary",
                "candidate_policy_id": "candidate@v2",
                "eligible": True,
                "arm": "candidate",
                "candidate_pct": 1.0,
                "assigned_at_ms": 1_000,
            },
        )
    )
    ledger = LiveCanaryLedger(
        EventLog(store, tenant="tenant-a"),
        experiment_id="tail-canary",
        candidate_policy_id="candidate@v2",
    )

    assert len(ledger._experiment_rows()) == 1
    first_cursor = ledger._append_cursor
    store.append_event(
        _event(
            "ordinary-2",
            event_type="decision_issued",
            decision_id="ordinary-decision",
        )
    )

    assert len(ledger._experiment_rows()) == 1
    assert ledger._append_cursor > first_cursor
    assert ledger._append_cursor == store.latest_append_seq(tenant_id="tenant-a")


def test_memory_store_never_reuses_sequence_after_retention() -> None:
    store = MemoryEventStore()
    store.append_event(
        _event(
            "event-1",
            event_type="decision_issued",
            decision_id="decision-1",
            user_id="user-a",
        )
    )
    store.append_event(
        _event(
            "event-2",
            event_type="decision_issued",
            decision_id="decision-2",
            user_id="user-b",
        )
    )
    consumed_cursor = store.latest_append_seq(tenant_id="tenant-a")

    assert store.delete_user_events(tenant_id="tenant-a", user_id="user-b") == 1
    store.append_event(
        _event(
            "event-3",
            event_type="decision_issued",
            decision_id="decision-3",
            user_id="user-c",
        )
    )
    new_rows = list(
        store.iter_events(
            tenant_id="tenant-a",
            after_append_seq=consumed_cursor,
        )
    )

    assert [row["event_id"] for row in new_rows] == ["event-3"]
    assert int(new_rows[0]["append_seq"]) > consumed_cursor
