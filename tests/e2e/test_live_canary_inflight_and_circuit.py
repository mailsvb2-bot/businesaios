from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from application.decision_runtime.run import _record_live_canary_assignment
from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.guardrails import CanaryDecision, GuardrailResult
from runtime.experiments.live_canary import LiveCanaryCoordinator


class InflightCoordinator:
    candidate_policy_id = "candidate@v2"

    def __init__(self, rollout_pct: float) -> None:
        self.rollout_pct = rollout_pct

    def live_rollout_pct(self):
        return self.rollout_pct


class ActiveRegistry:
    def __init__(self, active_policy_id: str) -> None:
        self.active_policy_id = active_policy_id

    def active_ref(self):
        return SimpleNamespace(policy_id=self.active_policy_id)


class InflightCore:
    def __init__(self, *, active_policy_id: str, rollout_pct: float) -> None:
        self._live_canary = InflightCoordinator(rollout_pct)
        self._selector = SimpleNamespace(
            _registry=ActiveRegistry(active_policy_id)
        )


def built(decision_id: str):
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=decision_id,
            correlation_id=f"correlation-{decision_id}",
        )
    )


def test_candidate_selected_before_rollback_is_rejected_after_rollout_clears() -> None:
    core = InflightCore(active_policy_id="active@v1", rollout_pct=0)

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_IN_FLIGHT_CANDIDATE_REVOKED",
    ):
        _record_live_canary_assignment(
            core=core,
            state={},
            policy=SimpleNamespace(id="candidate@v2"),
            out=SimpleNamespace(action="send_message@v1"),
            built=built("inflight-1"),
            tenant_id="tenant-a",
            subject_id="customer-1",
            expected_cost=0.0,
        )


def test_fully_promoted_active_candidate_is_not_treated_as_revoked() -> None:
    core = InflightCore(active_policy_id="candidate@v2", rollout_pct=0)

    _record_live_canary_assignment(
        core=core,
        state={},
        policy=SimpleNamespace(id="candidate@v2"),
        out=SimpleNamespace(action="send_message@v1"),
        built=built("promoted-1"),
        tenant_id="tenant-a",
        subject_id="customer-1",
        expected_cost=0.0,
    )


class CircuitEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(self, **kwargs):
        self.rows.append(dict(kwargs))
        return kwargs

    def iter_events(self):
        return iter(self.rows)


class CircuitRegistry:
    def rollout_config(self):
        return "candidate@v2", 1


def circuit_policy() -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="circuit-propagation",
        candidate_policy_id="candidate@v2",
        assignment_secret="c" * 32,
        candidate_pct=1.0,
        max_candidate_pct=1.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_purposes=("live_canary",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        min_assignments=100,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=60,
        outcome_window_seconds=60,
    )


def test_open_local_circuit_remains_a_rollback_decision() -> None:
    coordinator = LiveCanaryCoordinator(
        event_log=CircuitEvents(),
        policy_registry=CircuitRegistry(),
        candidate_policy_id="candidate@v2",
        policy=circuit_policy(),
    )
    opened = GuardrailResult(
        CanaryDecision.ROLLBACK,
        ("outcome_idempotency_conflict",),
        {"critical_violations": 1},
    )

    coordinator._open_local_circuit(
        opened,
        decision_id="circuit-1",
        correlation_id="circuit-correlation",
        tenant_id="tenant-a",
    )

    assert coordinator.rollback_required is True
    assert coordinator._guard_result() == opened


class RevalidationEvents(CircuitEvents):
    def get_events(self, decision_id, event_type):
        return [
            row
            for row in self.rows
            if row.get("decision_id") == decision_id
            and row.get("event_type") == event_type
        ]


class RevalidationRegistry:
    def __init__(self) -> None:
        self.reads = 0

    def rollout_config(self):
        self.reads += 1
        return "candidate@v2", (100 if self.reads < 3 else 0)

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")


def test_assignment_revalidates_rollout_immediately_before_return() -> None:
    coordinator = LiveCanaryCoordinator(
        event_log=RevalidationEvents(),
        policy_registry=RevalidationRegistry(),
        candidate_policy_id="candidate@v2",
        policy=replace(
            circuit_policy(),
            candidate_pct=100.0,
            max_candidate_pct=100.0,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_IN_FLIGHT_CANDIDATE_REVOKED",
    ):
        coordinator.assign(
            tenant_id="tenant-a",
            subject_id="customer-race",
            decision_id="race-revalidation",
            correlation_id="race-correlation",
            production_policy_id="active@v1",
            action="send_message@v1",
            purpose="live_canary",
            eligible=True,
        )


class CountingEvents(RevalidationEvents):
    def __init__(self) -> None:
        super().__init__()
        self.iter_calls = 0

    def iter_events(self):
        self.iter_calls += 1
        return iter(self.rows)


class StableRegistry:
    def rollout_config(self):
        return "candidate@v2", 100

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")


def test_assignment_guard_loads_evidence_once_not_per_request() -> None:
    events = CountingEvents()
    coordinator = LiveCanaryCoordinator(
        event_log=events,
        policy_registry=StableRegistry(),
        candidate_policy_id="candidate@v2",
        policy=replace(
            circuit_policy(),
            candidate_pct=100.0,
            max_candidate_pct=100.0,
            max_candidate_actions_per_day=1000,
            max_candidate_actions_per_subject_24h=1000,
        ),
    )

    for index in range(3):
        coordinator.assign(
            tenant_id="tenant-a",
            subject_id=f"customer-{index}",
            decision_id=f"bounded-{index}",
            correlation_id=f"bounded-correlation-{index}",
            production_policy_id="active@v1",
            action="send_message@v1",
            purpose="live_canary",
            eligible=True,
        )

    assert events.iter_calls == 1
