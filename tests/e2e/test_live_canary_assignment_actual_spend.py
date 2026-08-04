from __future__ import annotations

import time

from config.live_canary_policy import LiveCanaryPolicy
from core.events.log import EventLog
from core.experiments.guardrails import CanaryDecision, LiveCanaryGuard
from core.experiments.ledger import LiveCanaryLedger
from core.experiments.live_canary_events import (
    CANDIDATE_ACTION_EXECUTED,
    EXPERIMENT_ASSIGNMENT,
)
from core.experiments.repositories.live_canary_assignment_safety import (
    LiveCanaryAssignmentSafety,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _both_metrics(
    log: EventLog,
    *,
    experiment_id: str,
) -> tuple[dict[str, float | int], dict[str, float | int]]:
    safety = LiveCanaryAssignmentSafety(
        log,
        experiment_id=experiment_id,
        candidate_policy_id="candidate@v2",
    ).metrics(candidate_pct=1.0)
    ledger = LiveCanaryLedger(
        log,
        experiment_id=experiment_id,
        candidate_policy_id="candidate@v2",
    ).metrics(candidate_pct=1.0)
    return safety, ledger


def _emit_assignment(
    log: EventLog,
    *,
    experiment_id: str,
    decision_id: str,
    assigned_at_ms: int,
    expected_cost: float = 10.0,
) -> None:
    log.emit(
        event_type=EXPERIMENT_ASSIGNMENT,
        source="live_canary",
        user_id="experiment",
        decision_id=decision_id,
        correlation_id=f"correlation-{decision_id}",
        payload={
            "experiment_id": experiment_id,
            "candidate_policy_id": "candidate@v2",
            "tenant_id": "tenant-a",
            "purpose": "live_canary",
            "arm": "candidate",
            "candidate_pct": 1.0,
            "eligible": True,
            "subject_hash": f"subject-{decision_id}",
            "expected_cost": expected_cost,
            "assigned_at_ms": assigned_at_ms,
        },
    )


def _emit_execution(
    log: EventLog,
    *,
    experiment_id: str,
    decision_id: str,
    executed_at_ms: int,
    cost: float = 40.0,
) -> None:
    log.emit(
        event_type=CANDIDATE_ACTION_EXECUTED,
        source="live_canary",
        user_id="experiment",
        decision_id=decision_id,
        correlation_id=f"correlation-{decision_id}",
        payload={
            "experiment_id": experiment_id,
            "candidate_policy_id": "candidate@v2",
            "arm": "candidate",
            "cost": cost,
            "ok": True,
            "executed_at_ms": executed_at_ms,
        },
    )


def test_assignment_admission_replaces_executed_reservation_with_actual_cost() -> None:
    now_ms = int(time.time() * 1000)
    log = EventLog(MemoryEventStore(), tenant="tenant-a")
    common = {
        "experiment_id": "admission-cost",
        "candidate_policy_id": "candidate@v2",
        "tenant_id": "tenant-a",
        "purpose": "live_canary",
        "arm": "candidate",
        "candidate_pct": 1.0,
        "eligible": True,
        "assigned_at_ms": now_ms,
    }
    log.emit(
        event_type=EXPERIMENT_ASSIGNMENT,
        source="live_canary",
        user_id="experiment",
        decision_id="decision-1",
        correlation_id="correlation-1",
        payload={**common, "subject_hash": "subject-1", "expected_cost": 10.0},
    )
    log.emit(
        event_type=CANDIDATE_ACTION_EXECUTED,
        source="live_canary",
        user_id="experiment",
        decision_id="decision-1",
        correlation_id="correlation-1",
        payload={
            "experiment_id": "admission-cost",
            "candidate_policy_id": "candidate@v2",
            "arm": "candidate",
            "cost": 40.0,
            "ok": True,
            "executed_at_ms": now_ms,
        },
    )
    log.emit(
        event_type=EXPERIMENT_ASSIGNMENT,
        source="live_canary",
        user_id="experiment",
        decision_id="decision-2",
        correlation_id="correlation-2",
        payload={**common, "subject_hash": "subject-2", "expected_cost": 20.0},
    )

    safety = LiveCanaryAssignmentSafety(
        log,
        experiment_id="admission-cost",
        candidate_policy_id="candidate@v2",
    )
    metrics = safety.metrics(candidate_pct=1.0)

    assert metrics["candidate_expected_cost_24h"] == 30.0
    assert metrics["candidate_actual_cost_24h"] == 40.0
    assert metrics["candidate_cost_24h"] == 60.0

    policy = LiveCanaryPolicy(
        enabled=True,
        experiment_id="admission-cost",
        candidate_policy_id="candidate@v2",
        assignment_secret="s" * 32,
        candidate_pct=1.0,
        max_candidate_pct=1.0,
        initial_canary_pct=1,
        allowed_tenant_ids=("tenant-a",),
        max_daily_cost=50.0,
    )
    result = LiveCanaryGuard.evaluate(metrics, policy)

    assert result.decision is CanaryDecision.ROLLBACK
    assert "candidate_cost_budget" in result.reasons


def test_recent_execution_cost_survives_expired_assignment_reservation() -> None:
    now_ms = int(time.time() * 1000)
    old_assignment_ms = now_ms - 25 * 60 * 60 * 1000
    log = EventLog(MemoryEventStore(), tenant="tenant-a")
    experiment_id = "recent-spend"
    _emit_assignment(
        log,
        experiment_id=experiment_id,
        decision_id="old-assignment",
        assigned_at_ms=old_assignment_ms,
    )
    _emit_execution(
        log,
        experiment_id=experiment_id,
        decision_id="old-assignment",
        executed_at_ms=now_ms,
    )

    for metrics in _both_metrics(log, experiment_id=experiment_id):
        assert metrics["candidate_actions_24h"] == 0
        assert metrics["candidate_expected_cost_24h"] == 0.0
        assert metrics["candidate_actual_cost_24h"] == 40.0
        assert metrics["candidate_cost_24h"] == 40.0


def test_old_execution_does_not_resurrect_recent_assignment_reservation() -> None:
    now_ms = int(time.time() * 1000)
    old_execution_ms = now_ms - 25 * 60 * 60 * 1000
    log = EventLog(MemoryEventStore(), tenant="tenant-a")
    experiment_id = "old-execution"
    _emit_assignment(
        log,
        experiment_id=experiment_id,
        decision_id="recent-assignment",
        assigned_at_ms=now_ms,
    )
    _emit_execution(
        log,
        experiment_id=experiment_id,
        decision_id="recent-assignment",
        executed_at_ms=old_execution_ms,
    )

    for metrics in _both_metrics(log, experiment_id=experiment_id):
        assert metrics["candidate_actions_24h"] == 1
        assert metrics["candidate_expected_cost_24h"] == 10.0
        assert metrics["candidate_actual_cost_24h"] == 0.0
        assert metrics["candidate_cost_24h"] == 0.0


def test_expired_pending_assignment_leaves_no_rolling_exposure() -> None:
    now_ms = int(time.time() * 1000)
    log = EventLog(MemoryEventStore(), tenant="tenant-a")
    experiment_id = "expired-pending"
    _emit_assignment(
        log,
        experiment_id=experiment_id,
        decision_id="expired-pending",
        assigned_at_ms=now_ms - 25 * 60 * 60 * 1000,
    )

    for metrics in _both_metrics(log, experiment_id=experiment_id):
        assert metrics["candidate_actions_24h"] == 0
        assert metrics["candidate_expected_cost_24h"] == 0.0
        assert metrics["candidate_actual_cost_24h"] == 0.0
        assert metrics["candidate_cost_24h"] == 0.0


def test_recent_execution_replaces_recent_reservation_exactly_once() -> None:
    now_ms = int(time.time() * 1000)
    log = EventLog(MemoryEventStore(), tenant="tenant-a")
    experiment_id = "recent-replacement"
    _emit_assignment(
        log,
        experiment_id=experiment_id,
        decision_id="recent-execution",
        assigned_at_ms=now_ms,
    )
    _emit_execution(
        log,
        experiment_id=experiment_id,
        decision_id="recent-execution",
        executed_at_ms=now_ms,
    )

    for metrics in _both_metrics(log, experiment_id=experiment_id):
        assert metrics["candidate_actions_24h"] == 1
        assert metrics["candidate_expected_cost_24h"] == 10.0
        assert metrics["candidate_actual_cost_24h"] == 40.0
        assert metrics["candidate_cost_24h"] == 40.0
