from __future__ import annotations

from types import SimpleNamespace

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from core.ai import policy_registry as policy_registry_module
from runtime._internal.effects_actions import policy_actions
from runtime.boot import boot_decision_core


class BootRegistry:
    def __init__(
        self,
        candidate=None,
        rollout_pct: int = 0,
        governed_candidate=None,
    ) -> None:
        self.candidate = candidate
        self.rollout_pct = rollout_pct
        self.governed_candidate = governed_candidate
        self.mutations: list[dict] = []

    def rollout_config(self):
        return self.candidate, self.rollout_pct

    def governed_candidate_identity(self):
        return self.governed_candidate or self.candidate

    def snapshot_runtime_state(self):
        return (
            self.candidate,
            self.rollout_pct,
            self.governed_candidate,
            tuple(self.mutations),
        )

    def restore_runtime_state(self, snapshot):
        (
            self.candidate,
            self.rollout_pct,
            self.governed_candidate,
            mutations,
        ) = snapshot
        self.mutations = list(mutations)

    def set_rollout(self, **kwargs):
        self.mutations.append(dict(kwargs))
        raise AssertionError("unexpected rollout mutation")


class MemoryEvents:
    tenant_id = "tenant-a"

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(self, **kwargs):
        row = dict(kwargs)
        self.rows.append(row)
        return row

    def iter_events(self):
        return iter(self.rows)


class PolicyEffects(policy_actions.PolicyEffectsMixin):
    def __init__(self, registry: BootRegistry) -> None:
        self.event_log = MemoryEvents()
        self.policy_registry = registry


def configured_policy(candidate_policy_id: str) -> LiveCanaryPolicy:
    return LiveCanaryPolicy(
        enabled=True,
        experiment_id="boot-persistence-canary",
        candidate_policy_id=candidate_policy_id,
        assignment_secret="p" * 32,
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


def install_boot_spies(monkeypatch, policy, registry):
    calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        boot_decision_core,
        "DEFAULT_LIVE_CANARY_POLICY",
        policy,
    )
    monkeypatch.setattr(
        boot_decision_core,
        "attach_live_canary",
        lambda core, **kwargs: calls.append(
            ("attach", kwargs["candidate_policy_id"])
        ),
    )
    monkeypatch.setattr(
        boot_decision_core,
        "start_live_canary_runtime",
        lambda core: calls.append(("start", None)),
    )
    selector = SimpleNamespace(_registry=registry)
    return calls, selector


def install_deploy_spies(monkeypatch, policy) -> None:
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
        policy,
    )


def test_enabled_canary_boots_inactive_before_first_deployment(monkeypatch) -> None:
    registry = BootRegistry(candidate=None, rollout_pct=0)
    calls, selector = install_boot_spies(
        monkeypatch,
        configured_policy("candidate@v2"),
        registry,
    )

    boot_decision_core._attach_configured_live_canary(
        SimpleNamespace(), selector
    )

    assert calls == [("attach", "candidate@v2"), ("start", None)]
    assert registry.mutations == []


def test_restart_after_full_promotion_uses_persisted_candidate_at_zero_pct(
    monkeypatch,
) -> None:
    registry = BootRegistry(candidate=None, rollout_pct=0)
    calls, selector = install_boot_spies(
        monkeypatch,
        configured_policy("promoted-candidate@v3"),
        registry,
    )

    boot_decision_core._attach_configured_live_canary(
        SimpleNamespace(), selector
    )

    assert calls[0] == ("attach", "promoted-candidate@v3")
    assert registry.rollout_config() == (None, 0)
    assert registry.mutations == []


def test_boot_rejects_runtime_candidate_different_from_persisted_identity(
    monkeypatch,
) -> None:
    registry = BootRegistry(candidate="runtime-candidate@v4", rollout_pct=5)
    calls, selector = install_boot_spies(
        monkeypatch,
        configured_policy("configured-candidate@v2"),
        registry,
    )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_CANDIDATE_ID_MISMATCH",
    ):
        boot_decision_core._attach_configured_live_canary(
            SimpleNamespace(), selector
        )

    assert calls == []
    assert registry.mutations == []


def test_enabled_canary_without_any_candidate_identity_fails_closed(
    monkeypatch,
) -> None:
    registry = BootRegistry(candidate=None, rollout_pct=0)
    calls, selector = install_boot_spies(
        monkeypatch,
        configured_policy(""),
        registry,
    )

    with pytest.raises(RuntimeError, match="LIVE_CANARY_CANDIDATE_REQUIRED"):
        boot_decision_core._attach_configured_live_canary(
            SimpleNamespace(), selector
        )

    assert calls == []
    assert registry.mutations == []


def test_deploy_rejects_candidate_different_from_attached_identity(
    monkeypatch,
) -> None:
    registry = BootRegistry(candidate=None, rollout_pct=0)
    effects = PolicyEffects(registry)
    install_deploy_spies(
        monkeypatch,
        configured_policy("attached-candidate@v2"),
    )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_CANDIDATE_ID_MISMATCH",
    ):
        effects.deploy_policy(
            decision_id="deploy-drift",
            correlation_id="deploy-drift-correlation",
            tenant_id="tenant-a",
            candidate_policy_id="different-candidate@v3",
            rollout_pct=1,
        )

    assert registry.mutations == []


def test_programmatic_config_uses_runtime_candidate_as_effective_identity(
    monkeypatch,
) -> None:
    registry = BootRegistry(candidate="runtime-candidate@v2", rollout_pct=1)
    effects = PolicyEffects(registry)
    install_deploy_spies(monkeypatch, configured_policy(""))

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_CANDIDATE_ID_MISMATCH",
    ):
        effects.deploy_policy(
            decision_id="deploy-programmatic-drift",
            correlation_id="deploy-programmatic-drift-correlation",
            tenant_id="tenant-a",
            candidate_policy_id="different-candidate@v3",
            rollout_pct=1,
        )

    assert registry.mutations == []


def test_zero_percent_registration_cannot_change_governed_candidate_identity(
    monkeypatch,
) -> None:
    registry = BootRegistry(candidate="attached-candidate@v2", rollout_pct=0)
    effects = PolicyEffects(registry)
    install_deploy_spies(
        monkeypatch,
        configured_policy("attached-candidate@v2"),
    )

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_CANDIDATE_ID_MISMATCH",
    ):
        effects.deploy_policy(
            decision_id="register-shadow-drift",
            correlation_id="register-shadow-drift-correlation",
            tenant_id="tenant-a",
            candidate_policy_id="different-candidate@v3",
            rollout_pct=0,
        )

    assert registry.rollout_config() == ("attached-candidate@v2", 0)
    assert registry.mutations == []


def test_programmatic_identity_survives_cleared_rollout_after_promotion(
    monkeypatch,
) -> None:
    registry = BootRegistry(
        candidate=None,
        rollout_pct=0,
        governed_candidate="promoted-candidate@v2",
    )
    effects = PolicyEffects(registry)
    install_deploy_spies(monkeypatch, configured_policy(""))

    with pytest.raises(
        RuntimeError,
        match="LIVE_CANARY_CANDIDATE_ID_MISMATCH",
    ):
        effects.deploy_policy(
            decision_id="post-promotion-drift",
            correlation_id="post-promotion-drift-correlation",
            tenant_id="tenant-a",
            candidate_policy_id="different-candidate@v3",
            rollout_pct=1,
        )

    assert registry.governed_candidate_identity() == "promoted-candidate@v2"
    assert registry.mutations == []


def test_policy_registry_retains_governed_identity_after_full_promotion(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        policy_registry_module,
        "assert_called_from_bootstrap",
        lambda: None,
    )
    monkeypatch.setattr(
        policy_registry_module,
        "assert_called_from_runtime_executor",
        lambda: None,
    )
    registry = policy_registry_module.PolicyRegistry()
    registry.register(SimpleNamespace(id="active@v1"))
    registry.register(SimpleNamespace(id="candidate@v2"))

    registry.set_rollout(
        candidate_policy_id="candidate@v2",
        rollout_pct=100,
    )

    assert registry.rollout_config() == (None, 0)
    assert registry.active_ref().policy_id == "candidate@v2"
    assert registry.governed_candidate_identity() == "candidate@v2"
