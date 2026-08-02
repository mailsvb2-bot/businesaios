from __future__ import annotations

from types import SimpleNamespace

import pytest

from config.live_canary_policy import LiveCanaryPolicy
from runtime.boot import boot_decision_core


class BootRegistry:
    def __init__(self, candidate=None, rollout_pct: int = 0) -> None:
        self.candidate = candidate
        self.rollout_pct = rollout_pct
        self.mutations: list[dict] = []

    def rollout_config(self):
        return self.candidate, self.rollout_pct

    def set_rollout(self, **kwargs):
        self.mutations.append(dict(kwargs))
        raise AssertionError("boot must not enable candidate traffic")


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


def test_active_rollout_identity_overrides_persisted_boot_identity(
    monkeypatch,
) -> None:
    registry = BootRegistry(candidate="runtime-candidate@v4", rollout_pct=5)
    calls, selector = install_boot_spies(
        monkeypatch,
        configured_policy("configured-candidate@v2"),
        registry,
    )

    boot_decision_core._attach_configured_live_canary(
        SimpleNamespace(), selector
    )

    assert calls[0] == ("attach", "runtime-candidate@v4")
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
