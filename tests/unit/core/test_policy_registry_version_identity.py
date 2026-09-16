from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

import core.ai.policy_registry as registry_module
from core.policies.domain import PolicyRef


@dataclass(frozen=True)
class _Policy:
    id: str


def _allow_registry_mutations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_module, "assert_called_from_bootstrap", lambda: None)
    monkeypatch.setattr(registry_module, "assert_called_from_runtime_executor", lambda: None)


def test_policy_registry_preserves_real_version_through_rollout(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_registry_mutations(monkeypatch)
    registry = registry_module.PolicyRegistry()
    registry.register(_Policy("telegram_policy@v3"))
    registry.register(_Policy("candidate_policy@v7"))

    assert registry.active_ref() == PolicyRef("telegram_policy@v3", "v3")
    registry.set_rollout(candidate_policy_id="candidate_policy@v7", rollout_pct=25)
    assert registry.canary_ref() == PolicyRef("candidate_policy@v7", "v7")

    registry.set_rollout(candidate_policy_id="candidate_policy@v7", rollout_pct=100)
    assert registry.active_ref() == PolicyRef("candidate_policy@v7", "v7")
    registry.rollback()
    assert registry.active_ref() == PolicyRef("telegram_policy@v3", "v3")


def test_policy_registry_rejects_unversioned_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_registry_mutations(monkeypatch)
    registry = registry_module.PolicyRegistry()
    with pytest.raises(ValueError, match="POLICY_ID_MUST_BE_VERSIONED"):
        registry.register(_Policy("policy-without-version"))


def test_policy_registry_restore_rejects_version_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_registry_mutations(monkeypatch)
    registry = registry_module.PolicyRegistry()
    registry.register(_Policy("telegram_policy@v3"))
    snapshot = registry.snapshot_runtime_state()
    corrupted = replace(
        snapshot,
        lifecycle=replace(
            snapshot.lifecycle,
            active=PolicyRef("telegram_policy@v3", "v1"),
        ),
    )
    with pytest.raises(ValueError, match="POLICY_SNAPSHOT_VERSION_MISMATCH"):
        registry.restore_runtime_state(corrupted)
