from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.policies.domain import PolicyRef, PolicyStatus
from core.policies.registry import PolicyRegistry
from runtime._internal.effects_actions import policy_actions


class FakeEventLog:
    def __init__(self, *, tenant_id: str, fail_event: str | None = None) -> None:
        self.tenant_id = tenant_id
        self.fail_event = fail_event
        self.events: list[dict] = []

    def emit(self, **event) -> None:
        if event.get("event_type") == self.fail_event:
            raise RuntimeError("event-store-down")
        self.events.append(dict(event))


class FakeRuntimePolicyRegistry:
    def __init__(self) -> None:
        self.state = {
            "active": "policy-a",
            "candidate": None,
            "rollout_pct": 0,
            "canary": None,
            "previous": None,
        }
        self.restore_calls = 0

    def snapshot_runtime_state(self):
        return dict(self.state)

    def restore_runtime_state(self, snapshot) -> None:
        self.restore_calls += 1
        self.state = dict(snapshot)

    def set_rollout(self, *, candidate_policy_id: str, rollout_pct: int) -> None:
        self.state = {
            "active": candidate_policy_id if int(rollout_pct) >= 100 else self.state["active"],
            "candidate": None if int(rollout_pct) >= 100 else candidate_policy_id,
            "rollout_pct": 0 if int(rollout_pct) >= 100 else int(rollout_pct),
            "canary": None if int(rollout_pct) >= 100 else candidate_policy_id,
            "previous": self.state["active"] if int(rollout_pct) >= 100 else self.state["previous"],
        }

    def rollback(self) -> None:
        self.state = {
            "active": self.state["previous"] or self.state["active"],
            "candidate": None,
            "rollout_pct": 0,
            "canary": None,
            "previous": self.state["previous"],
        }


class FakePolicyEffects(policy_actions.PolicyEffectsMixin):
    def __init__(self, *, fail_event: str | None) -> None:
        self.event_log = FakeEventLog(tenant_id="business-a", fail_event=fail_event)
        self.policy_registry = FakeRuntimePolicyRegistry()


def test_lifecycle_registry_snapshot_restore_is_exact() -> None:
    registry = PolicyRegistry()
    active = PolicyRef(policy_id="policy-a", version="v1")
    canary = PolicyRef(policy_id="policy-b", version="v2")
    registry.promote(active)
    registry.register_candidate(canary)
    registry.start_canary(canary)
    before = registry.snapshot()

    registry.rollback()
    registry.promote(PolicyRef(policy_id="policy-c", version="v3"))
    registry.restore(before)

    assert registry.active() == active
    assert registry.canary() == canary
    assert registry.status("policy-a") == PolicyStatus.SAFE
    assert registry.status("policy-b") == PolicyStatus.CANARY
    assert registry.status("policy-c") is None
    assert registry.snapshot() == before


def test_failed_deploy_audit_restores_exact_pre_effect_registry_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy_actions, "assert_called_from_executor", lambda: None)
    effects = FakePolicyEffects(fail_event="policy_deployed")
    before = dict(effects.policy_registry.state)

    with pytest.raises(RuntimeError, match="event-store-down"):
        effects.deploy_policy(
            decision_id="decision-policy",
            correlation_id="correlation-policy",
            tenant_id="business-a",
            candidate_policy_id="policy-b",
            rollout_pct=100,
        )

    assert effects.policy_registry.state == before
    assert effects.policy_registry.restore_calls == 1
    assert effects.event_log.events == []


def test_failed_rollback_audit_restores_exact_pre_effect_registry_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy_actions, "assert_called_from_executor", lambda: None)
    effects = FakePolicyEffects(fail_event="policy_rolled_back")
    effects.policy_registry.state = {
        "active": "policy-b",
        "candidate": None,
        "rollout_pct": 0,
        "canary": None,
        "previous": "policy-a",
    }
    before = dict(effects.policy_registry.state)

    with pytest.raises(RuntimeError, match="event-store-down"):
        effects.rollback_policy(
            decision_id="decision-rollback",
            correlation_id="correlation-rollback",
            tenant_id="business-a",
            reason="bad metrics",
        )

    assert effects.policy_registry.state == before
    assert effects.policy_registry.restore_calls == 1
    assert effects.event_log.events == []


def test_policy_tenant_mismatch_blocks_before_registry_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy_actions, "assert_called_from_executor", lambda: None)
    effects = FakePolicyEffects(fail_event=None)
    snapshot_called = False

    def fail_snapshot():
        nonlocal snapshot_called
        snapshot_called = True
        raise AssertionError("snapshot must not be reached")

    effects.policy_registry.snapshot_runtime_state = fail_snapshot  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        effects.deploy_policy(
            decision_id="decision-policy",
            correlation_id="correlation-policy",
            tenant_id="business-b",
            candidate_policy_id="policy-b",
            rollout_pct=10,
        )

    assert snapshot_called is False
