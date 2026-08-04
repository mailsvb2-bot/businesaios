from __future__ import annotations

import time

from core.events.log import EventLog
from core.experiments.events.live_canary_events import (
    CANDIDATE_ACTION_EXECUTED,
    EXPERIMENT_ASSIGNMENT,
)
from core.experiments.repositories.live_canary_ledger import LiveCanaryLedger
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_actual_cost_replaces_only_its_own_assignment_reservation() -> None:
    now_ms = int(time.time() * 1000)
    log = EventLog(MemoryEventStore(), tenant="tenant-a")
    common = {
        "experiment_id": "cost-canary",
        "candidate_policy_id": "candidate@v2",
        "tenant_id": "tenant-a",
        "purpose": "live_canary",
        "arm": "candidate",
        "candidate_pct": 1.0,
        "expected_cost": 60.0,
        "eligible": True,
        "assigned_at_ms": now_ms,
    }
    for index in (1, 2):
        log.emit(
            event_type=EXPERIMENT_ASSIGNMENT,
            source="live_canary",
            user_id="experiment",
            decision_id=f"decision-{index}",
            correlation_id=f"correlation-{index}",
            payload={
                **common,
                "subject_hash": f"subject-{index}",
                "action": "send_message@v1",
            },
        )
    log.emit(
        event_type=CANDIDATE_ACTION_EXECUTED,
        source="live_canary",
        user_id="experiment",
        decision_id="decision-1",
        correlation_id="correlation-1",
        payload={
            "experiment_id": "cost-canary",
            "candidate_policy_id": "candidate@v2",
            "arm": "candidate",
            "action": "send_message@v1",
            "ok": True,
            "cost": 100.0,
            "executed_at_ms": now_ms,
        },
    )

    metrics = LiveCanaryLedger(
        log,
        experiment_id="cost-canary",
        candidate_policy_id="candidate@v2",
    ).metrics(candidate_pct=1.0)

    assert metrics["candidate_expected_cost_24h"] == 120.0
    assert metrics["candidate_actual_cost_24h"] == 100.0
    assert metrics["candidate_cost_24h"] == 160.0
