from __future__ import annotations

import time
from dataclasses import replace
from types import SimpleNamespace

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.live_canary_events import LIVE_CANARY_EXECUTION_FAILED_SOURCE
from runtime.experiments.hooks import record_live_canary_executor_exception
from runtime.experiments.live_canary import LiveCanaryCoordinator


class RaceEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.inject_foreign_on_retry = False
        self.injected = False

    def emit(self, **kwargs):
        row = dict(kwargs)
        self.rows.append(row)
        return row

    def iter_events(self):
        return iter(self.rows)

    def get_events(self, decision_id, event_type):
        if (
            self.inject_foreign_on_retry
            and not self.injected
            and decision_id == "bounded-idempotent"
            and event_type == "experiment_assignment@v1"
        ):
            self.injected = True
            self.rows.append(
                {
                    "event_type": "experiment_assignment@v1",
                    "decision_id": "foreign-between-refresh-and-observe",
                    "payload": {
                        "experiment_id": "final-review-races",
                        "candidate_policy_id": "candidate@v2",
                        "eligible": True,
                        "arm": "candidate",
                        "candidate_pct": 100.0,
                        "assigned_at_ms": int(time.time() * 1000),
                        "subject_hash": "foreign-subject",
                        "expected_cost": 7.0,
                    },
                }
            )
        return [
            row
            for row in self.rows
            if row.get("decision_id") == decision_id
            and row.get("event_type") == event_type
        ]


class Registry:
    def __init__(self) -> None:
        self.candidate_policy_id = "candidate@v2"
        self.rollout_pct = 100
        self.calls: list[dict] = []

    def rollout_config(self):
        return self.candidate_policy_id, self.rollout_pct

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")

    def snapshot_runtime_state(self):
        return self.rollout_pct, tuple(self.calls)

    def restore_runtime_state(self, snapshot):
        self.rollout_pct, calls = snapshot
        self.calls = list(calls)

    def set_rollout(self, **kwargs):
        self.candidate_policy_id = str(kwargs["candidate_policy_id"])
        self.rollout_pct = int(kwargs["rollout_pct"])
        self.calls.append(dict(kwargs))


def policy() -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="final-review-races",
        candidate_policy_id="candidate@v2",
        assignment_secret="f" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_purposes=("live_canary",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        max_candidate_actions_per_day=1000,
        max_candidate_actions_per_subject_24h=1000,
        max_daily_cost=1000.0,
        min_assignments=100,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=60,
        outcome_window_seconds=60,
    )


def test_idempotent_retry_scans_a_foreign_single_row_tail_increment() -> None:
    events = RaceEvents()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=Registry(),
        candidate_policy_id="candidate@v2",
        policy=policy(),
    )
    kwargs = {
        "tenant_id": "tenant-a",
        "subject_id": "customer-idempotent",
        "decision_id": "bounded-idempotent",
        "correlation_id": "bounded-idempotent-correlation",
        "production_policy_id": "active@v1",
        "action": "send_message@v1",
        "purpose": "live_canary",
        "eligible": True,
    }

    coordinator.assign(**kwargs)
    events.inject_foreign_on_retry = True
    coordinator.assign(**kwargs)

    metrics = coordinator._assignment_safety.metrics(candidate_pct=100.0)
    assert metrics["candidate_actions_24h"] == 2
    assert metrics["candidate_expected_cost_24h"] == 7.0


def test_executor_exception_with_zero_reservation_never_fabricates_cost() -> None:
    events = RaceEvents()
    registry = Registry()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=replace(policy(), max_daily_cost=1000.0),
    )
    decision_id = "exception-zero-cost"
    correlation_id = "exception-zero-cost-correlation"
    coordinator.assign(
        tenant_id="tenant-a",
        subject_id="customer-zero-cost",
        decision_id=decision_id,
        correlation_id=correlation_id,
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
        expected_cost=0.0,
    )
    executor = SimpleNamespace(
        _decision_core=SimpleNamespace(_live_canary=coordinator)
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=decision_id,
            correlation_id=correlation_id,
            action="send_message@v1",
            payload={"expected_cost": 0.0},
        )
    )

    record_live_canary_executor_exception(
        executor=executor,
        env=env,
        exc=RuntimeError("provider failed without cost evidence"),
    )

    assert len(
        events.get_events(decision_id, LIVE_CANARY_EXECUTION_FAILED_SOURCE)
    ) == 1
    assert events.get_events(decision_id, "candidate_action_executed@v1") == []
    assert len(
        events.get_events(
            f"execution-integrity:{decision_id}",
            "canary_auto_rolled_back@v1",
        )
    ) == 1
    assert registry.rollout_pct == 0
