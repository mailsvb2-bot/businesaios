from __future__ import annotations

import time

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.assignment import StableExperimentAssigner
from core.experiments.ledger import LiveCanaryLedger
from runtime.experiments.live_canary import (
    LiveCanaryCoordinator,
    source_event_evidence_ref,
)


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
            **{
                key: value
                for key, value in _kwargs.items()
                if key in {"event_id", "id", "external_id"}
            },
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
    def __init__(self, rollout_pct: int = 100) -> None:
        self.candidate_policy_id = "candidate@v2"
        self.rollout_pct = rollout_pct
        self.calls: list[dict] = []

    def rollout_config(self):
        return self.candidate_policy_id, self.rollout_pct

    def snapshot_runtime_state(self):
        return (self.rollout_pct, tuple(self.calls))

    def restore_runtime_state(self, snapshot):
        self.rollout_pct, calls = snapshot
        self.calls = list(calls)

    def set_rollout(self, **kwargs):
        self.rollout_pct = int(kwargs["rollout_pct"])
        self.calls.append(dict(kwargs))


def policy(candidate_pct: float = 100.0) -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="proof-bound-canary",
        assignment_secret="p" * 32,
        candidate_pct=candidate_pct,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        min_assignments=1,
        min_candidate_assignments=1,
        min_outcomes_per_arm=1,
        min_duration_seconds=0,
        outcome_window_seconds=60,
    )


def test_execution_and_revenue_require_non_stub_source_events() -> None:
    events = MemoryEvents()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=Registry(),
        candidate_policy_id="candidate@v2",
        policy=policy(),
    )
    assignment = coordinator.assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
    )
    assigned_at = events.get_events("d-1", "experiment_assignment@v1")[-1][
        "payload"
    ]["assigned_at_ms"]

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_VERIFIED_SOURCE_EVENT_REQUIRED",
    ):
        coordinator.record_execution(
            decision_id="d-1",
            correlation_id="c-1",
            arm=assignment.arm,
            action="send_message@v1",
            ok=True,
            cost=1.0,
            proof_event_type="message_sent",
            evidence_ref="telegram:1",
            executed_at_ms=assigned_at + 1,
        )

    events.emit(
        event_type="message_sent",
        source="telegram",
        user_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={"ok": True, "meta": {"mode": "stub"}},
    )
    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_VERIFIED_SOURCE_EVENT_REQUIRED",
    ):
        coordinator.record_execution(
            decision_id="d-1",
            correlation_id="c-1",
            arm=assignment.arm,
            action="send_message@v1",
            ok=True,
            cost=1.0,
            proof_event_type="message_sent",
            evidence_ref="telegram:1",
            executed_at_ms=assigned_at + 1,
        )

    events.emit(
        event_type="message_sent",
        source="telegram",
        user_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={"ok": True, "cost": 2.0},
    )
    execution = coordinator.record_execution(
        decision_id="d-1",
        correlation_id="c-1",
        arm=assignment.arm,
        action="send_message@v1",
        ok=True,
        cost=1.0,
        proof_event_type="message_sent",
        evidence_ref="telegram:1",
        executed_at_ms=assigned_at + 1,
    )
    assert execution["payload"]["cost"] == 2.0

    source_outcome = events.emit(
        event_type="booking_confirmed@v1",
        source="booking_webhook",
        user_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={"success": True, "amount": 3500.0},
    )
    outcome = coordinator.record_outcome(
        decision_id="d-1",
        correlation_id="c-1",
        arm=assignment.arm,
        outcome_type="booking_confirmed@v1",
        success=True,
        revenue=999_999.0,
        evidence_ref=source_event_evidence_ref(source_outcome),
        observed_at_ms=assigned_at + 2,
    )
    assert outcome["payload"]["revenue"] == 3500.0


def test_stage_metrics_are_isolated_and_only_mature_assignments_count() -> None:
    events = MemoryEvents()
    ledger = LiveCanaryLedger(
        events,
        experiment_id="stage-canary",
        candidate_policy_id="candidate@v2",
        outcome_window_seconds=1,
    )
    now_ms = int(time.time() * 1000)
    for decision_id, candidate_pct, assigned_at in (
        ("stage-1-old", 1.0, now_ms - 2_000),
        ("stage-1-new", 1.0, now_ms),
        ("stage-5-old", 5.0, now_ms - 2_000),
    ):
        assignment = StableExperimentAssigner(
            LiveCanaryPolicy(
                enabled=True,
                experiment_id="stage-canary",
                assignment_secret="q" * 32,
                candidate_pct=candidate_pct,
                max_candidate_pct=5.0,
                allowed_tenant_ids=("tenant-a",),
                allowed_actions=("send_message@v1",),
            )
        ).assign(
            tenant_id="tenant-a",
            subject_id=decision_id,
            candidate_policy_id="candidate@v2",
            action="send_message@v1",
            purpose="live_canary",
            eligible=True,
        )
        ledger.record_assignment(
            assignment,
            decision_id=decision_id,
            correlation_id=decision_id,
            production_policy_id="active@v1",
            action="send_message@v1",
            candidate_pct=candidate_pct,
            assigned_at_ms=assigned_at,
        )

    stage_one = ledger.metrics(candidate_pct=1.0)
    stage_five = ledger.metrics(candidate_pct=5.0)
    assert stage_one["assignment_count"] == 2
    assert stage_one["mature_assignment_count"] == 1
    assert stage_five["assignment_count"] == 1
    assert stage_five["mature_assignment_count"] == 1


def test_conflicting_replay_for_one_decision_is_rejected() -> None:
    events = MemoryEvents()
    ledger = LiveCanaryLedger(
        events,
        experiment_id="conflict-canary",
        candidate_policy_id="candidate@v2",
    )
    canary_policy = LiveCanaryPolicy(
        enabled=True,
        experiment_id="conflict-canary",
        assignment_secret="r" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
    )
    assignment = StableExperimentAssigner(canary_policy).assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        candidate_policy_id="candidate@v2",
        action="send_message@v1",
    )
    ledger.record_assignment(
        assignment,
        decision_id="d-1",
        correlation_id="c-1",
        production_policy_id="active@v1",
        action="send_message@v1",
        candidate_pct=100.0,
    )
    with pytest.raises(RuntimeError, match="LIVE_CANARY_IDEMPOTENCY_CONFLICT"):
        ledger.record_assignment(
            assignment,
            decision_id="d-1",
            correlation_id="c-1",
            production_policy_id="active@v1",
            action="noop@v1",
            candidate_pct=100.0,
        )


def test_outcome_values_come_from_exact_evidence_reference() -> None:
    events = MemoryEvents()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=Registry(),
        candidate_policy_id="candidate@v2",
        policy=policy(),
    )
    assignment = coordinator.assign(
        tenant_id="tenant-a",
        subject_id="customer-2",
        decision_id="d-exact",
        correlation_id="c-exact",
        production_policy_id="active@v1",
        action="send_message@v1",
        purpose="live_canary",
        eligible=True,
    )
    assigned_at = events.get_events(
        "d-exact", "experiment_assignment@v1"
    )[-1]["payload"]["assigned_at_ms"]
    older = events.emit(
        event_type="booking_confirmed@v1",
        source="booking_webhook",
        user_id="customer-2",
        decision_id="d-exact",
        correlation_id="c-exact",
        payload={"success": True, "amount": 100.0},
        event_id="booking-old",
    )
    events.emit(
        event_type="booking_confirmed@v1",
        source="booking_webhook",
        user_id="customer-2",
        decision_id="d-exact",
        correlation_id="c-exact",
        payload={"success": True, "amount": 900.0},
        event_id="booking-new",
    )
    outcome = coordinator.record_outcome(
        decision_id="d-exact",
        correlation_id="c-exact",
        arm=assignment.arm,
        outcome_type="booking_confirmed@v1",
        success=True,
        evidence_ref=source_event_evidence_ref(older),
        observed_at_ms=assigned_at + 1,
    )
    assert outcome["payload"]["revenue"] == 100.0
    assert outcome["payload"]["evidence_ref"] == "event:booking-old"
