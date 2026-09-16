from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import pytest

import core.ai.policy_registry as registry_module
from core.policies.domain import PolicyRef


@dataclass(frozen=True)
class _Policy:
    id: str


class _MemoryStateStore:
    def __init__(self) -> None:
        self.payload: dict | None = None

    def load(self):
        return deepcopy(self.payload)

    def save(self, payload, *, expected_generation: int) -> None:
        observed = 0 if self.payload is None else int(self.payload["rollout_generation"])
        if observed != int(expected_generation):
            raise RuntimeError("POLICY_RUNTIME_STATE_GENERATION_CONFLICT")
        self.payload = deepcopy(dict(payload))


def _allow_mutations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_module, "assert_called_from_bootstrap", lambda: None)
    monkeypatch.setattr(registry_module, "assert_called_from_runtime_executor", lambda: None)


def _registry(monkeypatch: pytest.MonkeyPatch, store: _MemoryStateStore):
    _allow_mutations(monkeypatch)
    registry = registry_module.PolicyRegistry(runtime_state_store=store)
    registry.register(_Policy("active@v1"))
    registry.register(_Policy("candidate@v2"))
    registry.activate_bootstrap(policy_id="active@v1")
    return registry


def test_policy_runtime_state_survives_restart_and_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _MemoryStateStore()
    first = _registry(monkeypatch, store)
    first.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=25)

    restarted = _registry(monkeypatch, store)
    assert restarted.restore_persisted_runtime_state() is True
    assert restarted.active_ref() == PolicyRef("active@v1", "v1")
    assert restarted.canary_ref() == PolicyRef("candidate@v2", "v2")
    assert restarted.rollout_config() == ("candidate@v2", 25)
    assert restarted.rollout_generation() == 1

    restarted.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=100)
    promoted = _registry(monkeypatch, store)
    assert promoted.restore_persisted_runtime_state() is True
    assert promoted.active_ref() == PolicyRef("candidate@v2", "v2")
    assert promoted.rollout_config() == (None, 0)
    assert promoted.rollout_generation() == 2

    promoted.rollback()
    rolled_back = _registry(monkeypatch, store)
    assert rolled_back.restore_persisted_runtime_state() is True
    assert rolled_back.active_ref() == PolicyRef("active@v1", "v1")
    assert rolled_back.rollout_generation() == 3


def test_policy_runtime_state_cas_conflict_reverts_local_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _MemoryStateStore()
    first = _registry(monkeypatch, store)
    first.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=10)

    stale = _registry(monkeypatch, store)
    assert stale.restore_persisted_runtime_state() is True
    first.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=20)

    with pytest.raises(RuntimeError, match="GENERATION_CONFLICT"):
        stale.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=30)
    assert stale.rollout_config() == ("candidate@v2", 10)
    assert stale.rollout_generation() == 1


def test_policy_runtime_state_rejects_unknown_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _MemoryStateStore()
    store.payload = {"schema_version": 999, "rollout_generation": 0}
    registry = _registry(monkeypatch, store)
    with pytest.raises(ValueError, match="SCHEMA_UNSUPPORTED"):
        registry.restore_persisted_runtime_state()


def test_rollout_zero_clears_canary_but_preserves_shadow_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _MemoryStateStore()
    registry = _registry(monkeypatch, store)
    registry.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=25)
    assert registry.canary_ref() == PolicyRef("candidate@v2", "v2")

    registry.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=0)
    assert registry.canary_ref() is None
    assert registry.rollout_config() == ("candidate@v2", 0)
    assert store.payload is not None
    assert store.payload["lifecycle"]["canary"] is None


def test_durable_restore_rolls_back_committed_mutation_with_monotonic_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _MemoryStateStore()
    registry = _registry(monkeypatch, store)
    before = registry.snapshot_runtime_state()
    registry.set_rollout(candidate_policy_id="candidate@v2", rollout_pct=25)
    assert registry.rollout_generation() == 1

    registry.restore_runtime_state(before)
    assert registry.rollout_config() == (None, 0)
    assert registry.canary_ref() is None
    assert registry.rollout_generation() == 2
    assert store.payload is not None
    assert store.payload["rollout_generation"] == 2

    restarted = _registry(monkeypatch, store)
    assert restarted.restore_persisted_runtime_state() is True
    assert restarted.rollout_config() == (None, 0)
    assert restarted.canary_ref() is None
    assert restarted.active_ref() == PolicyRef("active@v1", "v1")
    assert restarted.rollout_generation() == 2
