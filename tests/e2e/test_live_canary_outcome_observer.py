from __future__ import annotations

import time

from config.live_canary_policy import LiveCanaryPolicy
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
        **_kwargs,
    ):
        row = {
            "event_type": event_type,
            "source": source,
            "user_id": user_id,
            "payload": dict(payload),
            "decision_id": decision_id,
            "correlation_id": correlation_id,
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
    def __init__(self) -> None:
        self.rollout_pct = 100

    def rollout_config(self):
        return "candidate@v2", self.rollout_pct

    def snapshot_runtime_state(self):
        return self.rollout_pct

    def restore_runtime_state(self, snapshot):
        self.rollout_pct = snapshot

    def set_rollout(self, **kwargs):
        self.rollout_pct = int(kwargs["rollout_pct"])


def test_observer_attributes_real_webhook_once() -> None:
    events = MemoryEvents()
    policy = LiveCanaryPolicy(
        enabled=True,
        experiment_id="observer-canary",
        assignment_secret="o" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        max_candidate_actions_per_day=10,
        max_candidate_actions_per_subject_24h=1,
        max_daily_cost=100.0,
        min_assignments=100,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=60,
        outcome_window_seconds=60,
    )
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=Registry(),
        candidate_policy_id="candidate@v2",
        policy=policy,
    )
    coordinator.assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
    )
    events.emit(
        event_type="booking_confirmed@v1",
        source="booking_webhook",
        user_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={
            "success": True,
            "amount": 3500.0,
            "observed_at_ms": int(time.time() * 1000),
        },
    )
    observer = LiveCanaryOutcomeObserver(coordinator)
    assert observer.poll_once() == 1
    assert observer.poll_once() == 0
    outcomes = events.get_events("d-1", "business_outcome_observed@v1")
    assert len(outcomes) == 1
    assert outcomes[0]["payload"]["revenue"] == 3500.0
