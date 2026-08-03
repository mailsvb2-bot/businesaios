from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from runtime._internal.effects_actions import policy_actions


class Events:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(self, **kwargs):
        self.rows.append(dict(kwargs))
        return kwargs


class RacingRegistry:
    def __init__(self) -> None:
        self.generation = 7
        self.set_rollout_calls: list[dict] = []
        self.snapshot_calls = 0

    def rollout_generation(self) -> int:
        return self.generation

    def rollout_config(self):
        return "candidate@v2", 0

    def governed_candidate_identity(self):
        return "candidate@v2"

    def active_ref(self):
        return SimpleNamespace(policy_id="active@v1")

    @contextmanager
    def live_canary_assignment_window(self):
        # Simulate the watchdog completing rollback after deployment admission
        # but before the deployment mutation obtains the shared rollout lock.
        self.generation += 1
        yield

    def snapshot_runtime_state(self):
        self.snapshot_calls += 1
        return object()

    def restore_runtime_state(self, _snapshot):
        raise AssertionError("stale deployment must not mutate or restore registry")

    def set_rollout(self, **kwargs):
        self.set_rollout_calls.append(dict(kwargs))


class Effects(policy_actions.PolicyEffectsMixin):
    def __init__(self) -> None:
        self.event_log = Events()
        self.policy_registry = RacingRegistry()

    def _require_live_canary_evidence(self, **_kwargs) -> str:
        return "deployment-generation-race"


def configured_policy() -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="deployment-generation-race",
        candidate_policy_id="candidate@v2",
        assignment_secret="g" * 32,
        candidate_pct=1.0,
        max_candidate_pct=1.0,
        initial_canary_pct=1,
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


def test_watchdog_rollback_generation_prevents_stale_deployment_revive(
    monkeypatch,
) -> None:
    monkeypatch.setattr(policy_actions, "assert_called_from_executor", lambda: None)
    monkeypatch.setattr(
        policy_actions,
        "assert_event_log_tenant",
        lambda _event_log, *, tenant_id, operation: tenant_id,
    )
    monkeypatch.setattr(
        policy_actions.RolloutGuard,
        "allow_promotion",
        lambda _metrics: True,
    )
    monkeypatch.setattr(
        policy_actions,
        "DEFAULT_LIVE_CANARY_POLICY",
        configured_policy(),
    )
    effects = Effects()

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_ROLLOUT_GENERATION_CHANGED",
    ):
        effects.deploy_policy(
            decision_id="stale-deploy",
            correlation_id="stale-deploy-correlation",
            tenant_id="tenant-a",
            candidate_policy_id="candidate@v2",
            rollout_pct=1,
        )

    assert effects.policy_registry.snapshot_calls == 0
    assert effects.policy_registry.set_rollout_calls == []
    assert effects.event_log.rows == []
