from __future__ import annotations

from dataclasses import replace

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.assignment import ExperimentArm
from core.experiments.guardrails import CanaryDecision, LiveCanaryGuard
from runtime.experiments.live_canary import (
    LiveCanaryCoordinator,
    source_event_evidence_ref,
)


class Registry:
    def __init__(self, *, rollout_pct: int = 100) -> None:
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


class AuditFailureEvents:
    tenant_id = "tenant-a"

    def iter_events(self):
        raise OSError("ledger unavailable")

    def emit(self, **_kwargs):
        raise OSError("audit unavailable")


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


def policy(**overrides) -> LiveCanaryPolicy:
    base = LiveCanaryPolicy(
        enabled=True,
        experiment_id="metro-followup-2026-08",
        assignment_secret="z" * 32,
        candidate_pct=100.0,
        max_candidate_pct=100.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        max_candidate_actions_per_day=50,
        max_candidate_actions_per_subject_24h=1,
        max_daily_cost=100.0,
        min_assignments=1,
        min_candidate_assignments=1,
        min_outcomes_per_arm=1,
        min_duration_seconds=0,
        outcome_window_seconds=60,
    )
    return replace(base, **overrides)


def test_audit_failure_does_not_restore_candidate_after_rollback() -> None:
    registry = Registry()
    coordinator = LiveCanaryCoordinator(
        event_log=AuditFailureEvents(),
        policy_registry=registry,
        candidate_policy_id="candidate@v2",
        policy=policy(),
    )
    with pytest.raises(OSError, match="audit unavailable"):
        coordinator.evaluate_and_maybe_rollback(
            decision_id="watchdog-1",
            correlation_id="c-1",
            tenant_id="tenant-a",
        )
    assert registry.calls[-1]["rollout_pct"] == 0


def test_rolling_cost_and_frequency_limits_force_rollback() -> None:
    canary_policy = policy(candidate_pct=1.0)
    metrics = {
        "candidate_actions_24h": 51,
        "candidate_cost_24h": 101.0,
        "candidate_max_actions_per_subject_24h": 2,
        "candidate_executions": 51,
        "candidate_errors": 0,
        "candidate_complaints": 0,
        "assignment_count": 51,
        "critical_violations": 0,
    }
    result = LiveCanaryGuard.evaluate(metrics, canary_policy)
    assert result.decision is CanaryDecision.ROLLBACK
    assert "candidate_cost_budget" in result.reasons
    assert "candidate_action_frequency" in result.reasons
    assert "candidate_subject_frequency" in result.reasons


def test_outcome_requires_assignment_arm_source_proof_and_window() -> None:
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
    assert assignment.arm is ExperimentArm.CANDIDATE
    assigned = events.get_events("d-1", "experiment_assignment@v1")[-1][
        "payload"
    ]["assigned_at_ms"]

    with pytest.raises(RuntimeError, match="LIVE_CANARY_OUTCOME_ARM_MISMATCH"):
        coordinator.record_outcome(
            decision_id="d-1",
            correlation_id="c-1",
            arm=ExperimentArm.CONTROL,
            outcome_type="booking_confirmed@v1",
            success=True,
            evidence_ref="booking:1",
            observed_at_ms=assigned + 1,
        )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_VERIFIED_SOURCE_EVENT_REQUIRED",
    ):
        coordinator.record_outcome(
            decision_id="d-1",
            correlation_id="c-1",
            arm=ExperimentArm.CANDIDATE,
            outcome_type="booking_confirmed@v1",
            success=True,
            evidence_ref="event:missing",
            observed_at_ms=assigned + 1,
        )

    source_outcome = events.emit(
        event_type="booking_confirmed@v1",
        source="booking_webhook",
        user_id="customer-1",
        decision_id="d-1",
        correlation_id="c-1",
        payload={"success": True, "amount": 3500.0},
    )
    with pytest.raises(RuntimeError, match="LIVE_CANARY_OUTCOME_WINDOW_EXPIRED"):
        coordinator.record_outcome(
            decision_id="d-1",
            correlation_id="c-1",
            arm=ExperimentArm.CANDIDATE,
            outcome_type="booking_confirmed@v1",
            success=True,
            evidence_ref=source_event_evidence_ref(source_outcome),
            observed_at_ms=assigned + 61_000,
        )
