from __future__ import annotations

import time

from config.live_canary_policy import LiveCanaryPolicy
from core.events.log import EventLog
from core.experiments.guardrails import CanaryDecision, LiveCanaryGuard
from core.experiments.live_canary_events import (
    CANDIDATE_ACTION_EXECUTED,
    EXPERIMENT_ASSIGNMENT,
)
from core.experiments.repositories.live_canary_assignment_safety import (
    LiveCanaryAssignmentSafety,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


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
