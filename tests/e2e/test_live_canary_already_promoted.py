from __future__ import annotations

from types import SimpleNamespace

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from runtime._internal.effects_actions import policy_actions


class Registry:
    def __init__(self) -> None:
        self.mutations: list[dict] = []

    def rollout_config(self):
        return None, 0

    def governed_candidate_identity(self):
        return "candidate@v2"

    def active_ref(self):
        return SimpleNamespace(policy_id="candidate@v2")

    def snapshot_runtime_state(self):
        raise AssertionError("already-promoted request must fail before snapshot")

    def set_rollout(self, **kwargs):
        self.mutations.append(dict(kwargs))
        raise AssertionError("already-promoted request must not mutate rollout")


class Events:
    tenant_id = "tenant-a"

    def iter_events(self):
        return iter(())


class Effects(policy_actions.PolicyEffectsMixin):
    def __init__(self) -> None:
        self.event_log = Events()
        self.policy_registry = Registry()


def policy() -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="already-promoted-canary",
        candidate_policy_id="candidate@v2",
        assignment_secret="a" * 32,
        candidate_pct=1.0,
        max_candidate_pct=10.0,
        allowed_tenant_ids=("tenant-a",),
        allowed_purposes=("live_canary",),
        allowed_actions=("send_message@v1",),
        outcome_event_types=("booking_confirmed@v1",),
        min_assignments=100,
        min_candidate_assignments=10,
        min_outcomes_per_arm=10,
        min_duration_seconds=60,
        outcome_window_seconds=60,
        outcome_poll_seconds=1.0,
    )


def test_positive_rollout_of_already_active_candidate_is_rejected(
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
        policy(),
    )
    effects = Effects()

    with pytest.raises(RuntimeError, match="LIVE_CANARY_ALREADY_PROMOTED"):
        effects.deploy_policy(
            decision_id="redeploy-promoted",
            correlation_id="redeploy-promoted-correlation",
            tenant_id="tenant-a",
            candidate_policy_id="candidate@v2",
            rollout_pct=1,
        )

    assert effects.policy_registry.mutations == []
