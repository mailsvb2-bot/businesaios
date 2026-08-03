from __future__ import annotations

import time

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.live_canary_events import BUSINESS_OUTCOME_OBSERVED
from runtime.experiments.live_canary import LiveCanaryCoordinator
from runtime.experiments.outcome_observer import LiveCanaryOutcomeObserver


class MemoryEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(
        self,
        *,
        event_type,
        source,
        user_id,
        payload,
        decision_id=None,
        correlation_id=None,
        timestamp_ms=None,
        event_id=None,
        **_kwargs,
    ):
        row = {
            "event_id": event_id,
            "tenant_id": self.tenant_id,
            "event_type": event_type,
            "source": source,
            "user_id": user_id,
            "payload": dict(payload),
            "decision_id": decision_id,
            "correlation_id": correlation_id,
            "timestamp_ms": int(timestamp_ms or time.time() * 1000),
        }
        self.rows.append(row)
        return row

    def get_events(self, decision_id, event_type):
        return [
            row
            for row in self.rows
            if row["decision_id"] == decision_id
            and row["event_type"] == event_type
        ]

    def iter_events(self):
        return iter(self.rows)


class Registry:
    def rollout_config(self):
        return "candidate@v2", 100


def policy() -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="semantic-consistency",
        assignment_secret="s" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        max_candidate_actions_per_day=10,
        max_candidate_actions_per_subject_24h=10,
        max_daily_cost=100.0,
        min_assignments=100,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=60,
        outcome_window_seconds=60,
    )


def test_conflicting_boolean_fields_have_one_outcome_interpretation() -> None:
    events = MemoryEvents()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=Registry(),
        candidate_policy_id="candidate@v2",
        policy=policy(),
    )
    coordinator.assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        decision_id="decision-1",
        correlation_id="correlation-1",
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
    )
    events.emit(
        event_type="booking_confirmed@v1",
        source="booking_webhook",
        user_id="customer-1",
        decision_id="decision-1",
        correlation_id="correlation-1",
        payload={
            "success": True,
            "ok": False,
            "amount": 2500.0,
        },
    )

    observer = LiveCanaryOutcomeObserver(coordinator)

    assert observer.poll_once() == 1
    recorded = events.get_events("decision-1", BUSINESS_OUTCOME_OBSERVED)
    assert len(recorded) == 1
    assert recorded[0]["payload"]["success"] is True
    assert recorded[0]["payload"]["revenue"] == 2500.0
