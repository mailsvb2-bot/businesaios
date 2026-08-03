from __future__ import annotations

from dataclasses import replace

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.assignment import ExperimentArm, StableExperimentAssigner
from core.experiments.events import (
    BUSINESS_OUTCOME_OBSERVED,
    CANARY_AUTO_ROLLED_BACK,
    EXPERIMENT_ASSIGNMENT,
    is_live_canary_event,
)
from core.experiments.guardrails import CanaryDecision, LiveCanaryGuard
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
    def __init__(self, *, rollout_pct: int = 0) -> None:
        self.calls: list[dict] = []
        self.candidate_policy_id = "candidate@v2"
        self.rollout_pct = rollout_pct

    def snapshot_runtime_state(self):
        return (tuple(self.calls), self.rollout_pct)

    def restore_runtime_state(self, snapshot):
        calls, self.rollout_pct = snapshot
        self.calls = list(calls)

    def set_rollout(self, **kwargs):
        self.calls.append(dict(kwargs))
        self.candidate_policy_id = str(kwargs["candidate_policy_id"])
        self.rollout_pct = int(kwargs["rollout_pct"])

    def rollout_config(self):
        return self.candidate_policy_id, self.rollout_pct


def policy(**overrides):
    base = LiveCanaryPolicy(
        enabled=True,
        experiment_id="metro-followup-2026-08",
        assignment_secret="s" * 32,
        candidate_pct=1.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        min_assignments=1,
        min_candidate_assignments=1,
        min_outcomes_per_arm=1,
        min_duration_seconds=0,
        outcome_window_seconds=1,
        max_daily_cost=1000.0,
    )
    return replace(base, **overrides)


def test_assignment_is_stable_secret_backed_and_tenant_scoped() -> None:
    assigner = StableExperimentAssigner(policy(candidate_pct=50.0))
    first = assigner.assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        candidate_policy_id="candidate@v2",
        action="send_message@v1",
    )
    second = assigner.assign(
        tenant_id="tenant-a",
        subject_id="customer-1",
        candidate_policy_id="candidate@v2",
        action="send_message@v1",
    )
    other_tenant = assigner.assign(
        tenant_id="tenant-b",
        subject_id="customer-1",
        candidate_policy_id="candidate@v2",
        action="send_message@v1",
    )
    assert first == second
    assert first.subject_hash and "customer-1" not in first.subject_hash
    assert other_tenant.arm is ExperimentArm.INELIGIBLE
    assert other_tenant.reason == "tenant_not_allowed"


def test_control_is_not_excluded_by_candidate_action_allowlist() -> None:
    assigner = StableExperimentAssigner(policy(candidate_pct=1.0))
    controls = [
        assigner.assign(
            tenant_id="tenant-a",
            subject_id=f"control-{index}",
            candidate_policy_id="candidate@v2",
            action="noop@v1",
        )
        for index in range(500)
    ]
    assert any(row.arm is ExperimentArm.CONTROL for row in controls)
    assert all(
        row.reason != "candidate_action_not_allowed"
        for row in controls
        if row.arm is ExperimentArm.CONTROL
    )


def test_distribution_is_close_to_configured_one_percent() -> None:
    assigner = StableExperimentAssigner(policy())
    assignments = [
        assigner.assign(
            tenant_id="tenant-a",
            subject_id=f"customer-{index}",
            candidate_policy_id="candidate@v2",
            action="send_message@v1",
        )
        for index in range(10_000)
    ]
    candidates = sum(
        row.arm is ExperimentArm.CANDIDATE for row in assignments
    )
    assert 70 <= candidates <= 130


def test_real_outcomes_are_idempotent_and_event_backed() -> None:
    events = MemoryEvents()
    ledger = LiveCanaryLedger(
        events,
        experiment_id="metro-followup-2026-08",
        candidate_policy_id="candidate@v2",
    )
    assignment = StableExperimentAssigner(
        policy(candidate_pct=100.0)
    ).assign(
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
    ledger.record_execution(
        decision_id="d-1",
        correlation_id="c-1",
        arm=assignment.arm,
        action="send_message@v1",
        ok=True,
        cost=1.0,
        proof_event_type="message_sent",
        evidence_ref="telegram:update:1",
    )
    for _ in range(2):
        ledger.record_outcome(
            decision_id="d-1",
            correlation_id="c-1",
            arm=assignment.arm,
            outcome_type="booking_confirmed@v1",
            success=True,
            revenue=3500.0,
            evidence_ref="booking:1",
        )
    metrics = ledger.metrics(candidate_pct=100.0)
    assert metrics["candidate_assignments"] == 1
    assert metrics["candidate_outcomes"] == 1
    assert metrics["candidate_successes"] == 1
    assert metrics["candidate_revenue"] == 3500.0
    assert events.get_events("d-1", EXPERIMENT_ASSIGNMENT)
    assert events.get_events("d-1", BUSINESS_OUTCOME_OBSERVED)


def test_guard_is_fail_closed_and_rolls_back_on_critical_violation() -> None:
    events = MemoryEvents()
    registry = Registry(rollout_pct=100)
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=policy(candidate_pct=100.0),
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
    failure_proof = events.emit(
        event_type="message_failed",
        source="telegram",
        user_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={"ok": False},
    )
    coordinator.record_execution(
        decision_id="d-1",
        correlation_id="c-1",
        arm=assignment.arm,
        action="send_message@v1",
        ok=False,
        cost=0.0,
        proof_event_type="message_failed",
        evidence_ref=source_event_evidence_ref(failure_proof),
        critical_violation=True,
    )
    result = coordinator.evaluate_and_maybe_rollback(
        decision_id="rollback-1",
        correlation_id="c-rollback",
        tenant_id="tenant-a",
    )
    assert result.decision is CanaryDecision.ROLLBACK
    assert registry.calls[-1]["rollout_pct"] == 0
    assert events.get_events("rollback-1", CANARY_AUTO_ROLLED_BACK)


def test_guard_promotes_only_with_real_noninferior_business_outcomes() -> None:
    canary_policy = policy(candidate_pct=50.0, max_sample_ratio_z=10.0)
    metrics = {
        "control_assignments": 1000,
        "candidate_assignments": 1000,
        "control_executions": 1000,
        "candidate_executions": 1000,
        "control_errors": 0,
        "candidate_errors": 0,
        "control_complaints": 0,
        "candidate_complaints": 0,
        "control_cost": 100.0,
        "candidate_cost": 100.0,
        "control_outcomes": 1000,
        "candidate_outcomes": 1000,
        "control_successes": 400,
        "candidate_successes": 450,
        "control_revenue": 4000.0,
        "candidate_revenue": 4500.0,
        "critical_violations": 0,
        "assignment_count": 2000,
        "duration_seconds": 86_400,
    }
    assert (
        LiveCanaryGuard.evaluate(metrics, canary_policy).decision
        is CanaryDecision.PROMOTE
    )
    degraded = {**metrics, "candidate_successes": 100}
    assert (
        LiveCanaryGuard.evaluate(degraded, canary_policy).decision
        is CanaryDecision.ROLLBACK
    )
    assert (
        LiveCanaryGuard.evaluate({}, canary_policy).decision
        is CanaryDecision.CONTINUE
    )


def test_candidate_cannot_execute_non_allowlisted_action() -> None:
    coordinator = LiveCanaryCoordinator(
        event_log=MemoryEvents(),
        policy_registry=Registry(rollout_pct=100),
        candidate_policy_id="candidate@v2",
        policy=policy(candidate_pct=100.0),
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
    with pytest.raises(RuntimeError, match="LIVE_CANARY_ACTION_BLOCKED"):
        coordinator.assert_candidate_action_allowed(
            assignment,
            action="capture_payment@v1",
        )


def test_event_vocabulary_contains_live_canary_evidence() -> None:
    assert is_live_canary_event(EXPERIMENT_ASSIGNMENT)
    assert is_live_canary_event(BUSINESS_OUTCOME_OBSERVED)
    assert is_live_canary_event(CANARY_AUTO_ROLLED_BACK)
