from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from application.decision_runtime.run import _record_live_canary_assignment
from core.policies.selector import LiveCanaryRoutingSnapshot


class FakeRegistry:
    def __init__(self, *, generation: int = 2) -> None:
        self.generation = generation

    @contextmanager
    def live_canary_assignment_window(self):
        yield

    def rollout_config(self):
        return "candidate@v2", 1

    def rollout_generation(self) -> int:
        return self.generation

    def active(self):
        return SimpleNamespace(id="active@v1")


class FakeCoordinator:
    candidate_policy_id = "candidate@v2"
    policy = SimpleNamespace(eligibility_state_key="live_canary_eligible")

    def __init__(self) -> None:
        self.assign_calls = 0

    def live_rollout_pct(self) -> float:
        return 1.0

    def assign(self, **_kwargs):
        self.assign_calls += 1
        raise AssertionError("assignment must not be recorded")


def _built():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
        )
    )


def _record(
    *,
    registry: FakeRegistry,
    coordinator: FakeCoordinator,
    snapshot: LiveCanaryRoutingSnapshot,
) -> None:
    core = SimpleNamespace(
        _live_canary=coordinator,
        _selector=SimpleNamespace(_registry=registry),
    )
    _record_live_canary_assignment(
        core=core,
        state={
            "purpose": "live_canary",
            "live_canary_eligible": True,
        },
        policy=SimpleNamespace(id="active@v1"),
        out=SimpleNamespace(action="send_message@v1"),
        built=_built(),
        tenant_id="tenant-a",
        subject_id="customer-1",
        expected_cost=1.0,
        routing_snapshot=snapshot,
    )


def test_generation_change_aborts_before_assignment_reservation() -> None:
    registry = FakeRegistry(generation=2)
    coordinator = FakeCoordinator()
    snapshot = LiveCanaryRoutingSnapshot(
        candidate_policy_id="candidate@v2",
        rollout_pct=1,
        rollout_generation=1,
        active_policy_id="active@v1",
        selected_policy_id="active@v1",
    )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_ROLLOUT_CHANGED_DURING_DECISION",
    ):
        _record(registry=registry, coordinator=coordinator, snapshot=snapshot)

    assert coordinator.assign_calls == 0


def test_zero_to_live_transition_aborts_pre_rollout_selection() -> None:
    registry = FakeRegistry(generation=1)
    coordinator = FakeCoordinator()
    snapshot = LiveCanaryRoutingSnapshot(
        candidate_policy_id="",
        rollout_pct=0,
        rollout_generation=0,
        active_policy_id="active@v1",
        selected_policy_id="active@v1",
    )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_CANDIDATE_ID_MISMATCH",
    ):
        _record(registry=registry, coordinator=coordinator, snapshot=snapshot)

    assert coordinator.assign_calls == 0


def test_safe_mode_policy_is_not_recorded_as_control() -> None:
    registry = FakeRegistry()
    coordinator = FakeCoordinator()
    core = SimpleNamespace(
        _live_canary=coordinator,
        _selector=SimpleNamespace(_registry=registry),
    )

    _record_live_canary_assignment(
        core=core,
        state={
            "purpose": "live_canary",
            "safe_mode": True,
            "live_canary_eligible": True,
        },
        policy=SimpleNamespace(id="safe@v1"),
        out=SimpleNamespace(action="send_message@v1"),
        built=_built(),
        tenant_id="tenant-a",
        subject_id="customer-1",
        expected_cost=1.0,
    )

    assert coordinator.assign_calls == 0


def test_safe_mode_can_never_route_candidate() -> None:
    registry = FakeRegistry()
    coordinator = FakeCoordinator()
    core = SimpleNamespace(
        _live_canary=coordinator,
        _selector=SimpleNamespace(_registry=registry),
    )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_SAFE_MODE_CANDIDATE_SELECTED",
    ):
        _record_live_canary_assignment(
            core=core,
            state={
                "purpose": "live_canary",
                "safe_mode": True,
                "live_canary_eligible": True,
            },
            policy=SimpleNamespace(id="candidate@v2"),
            out=SimpleNamespace(action="send_message@v1"),
            built=_built(),
            tenant_id="tenant-a",
            subject_id="customer-1",
            expected_cost=1.0,
        )

    assert coordinator.assign_calls == 0
