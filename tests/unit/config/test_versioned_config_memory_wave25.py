from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from config.policy_config_store import InMemoryPolicyConfigStore, PolicyConfigSnapshot
from config.runtime_config_store import InMemoryRuntimeConfigStore, RuntimeConfigSnapshot

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_in_memory_stores_share_one_versioning_owner_and_defensive_copy_contract() -> None:
    policy = InMemoryPolicyConfigStore()
    original_config = {"nested": {"value": 1}}
    first = policy.save(
        PolicyConfigSnapshot(policy_name="pricing", tenant_id="tenant-a", scope="product", config=original_config, updated_at=NOW),
        actor="owner",
        reason="initial",
    )
    assert first.version is not None and first.version.revision == 1
    original_config["nested"]["value"] = 99
    cast(dict, first.config)["nested"]["value"] = 88
    assert policy.get(policy_name="pricing", tenant_id="tenant-a", scope="product") is not None
    assert policy.require(policy_name="pricing", tenant_id="tenant-a", scope="product").config == {"nested": {"value": 1}}

    idempotent = policy.save(
        PolicyConfigSnapshot(policy_name="pricing", tenant_id="tenant-a", scope="product", config={"nested": {"value": 1}}, updated_at=NOW)
    )
    assert idempotent.version == first.version
    assert len(policy.history(policy_name="pricing", tenant_id="tenant-a", scope="product")) == 1

    second = policy.save(
        PolicyConfigSnapshot(policy_name="pricing", tenant_id="tenant-a", scope="product", config={"nested": {"value": 2}}, updated_at=NOW),
        expected_revision=1,
    )
    assert second.version is not None and second.version.revision == 2
    assert second.version.parent_fingerprint == first.version.fingerprint
    history = policy.history(policy_name="pricing", tenant_id="tenant-a", scope="product")
    cast(dict, history[0].config)["nested"]["value"] = 500
    assert policy.history(policy_name="pricing", tenant_id="tenant-a", scope="product")[0].config == {"nested": {"value": 1}}
    assert policy.list_all() == (second,)

    with pytest.raises(KeyError):
        policy.require(policy_name="missing")
    with pytest.raises(RuntimeError):
        policy.save(PolicyConfigSnapshot(policy_name="missing", updated_at=NOW), expected_revision=1)
    with pytest.raises(RuntimeError):
        policy.save(PolicyConfigSnapshot(policy_name="pricing", tenant_id="tenant-a", scope="product", config={"nested": {"value": 3}}, updated_at=NOW), expected_revision=1)
    with pytest.raises(ValueError):
        policy.save(cast(PolicyConfigSnapshot, object()))
    with pytest.raises(ValueError):
        policy.save(PolicyConfigSnapshot(policy_name="x", updated_at=NOW), actor="")
    with pytest.raises(ValueError):
        policy.save(PolicyConfigSnapshot(policy_name="x", updated_at=NOW), reason=cast(str, None))

    runtime = InMemoryRuntimeConfigStore()
    prod = runtime.save(RuntimeConfigSnapshot(profile_name="api", environment="production", runtime_settings={"workers": 2}, updated_at=NOW))
    dev = runtime.save(RuntimeConfigSnapshot(profile_name="api", environment="local", runtime_settings={"workers": 1}, updated_at=NOW))
    assert runtime.get(profile_name="api", environment="prod") == prod
    assert runtime.get(profile_name="api", environment="development") == dev
    assert [item.environment for item in runtime.list_all()] == ["dev", "prod"]
    assert runtime.history(profile_name="api", environment="prod") == (prod,)
    with pytest.raises(KeyError):
        runtime.require(profile_name="missing", environment="prod")

def test_legacy_unversioned_snapshot_expected_revision_compatibility() -> None:
    store = InMemoryPolicyConfigStore()
    legacy = PolicyConfigSnapshot(policy_name="legacy-policy", config={"x": 1}, updated_at=NOW)
    key = store._snapshot_key(legacy)
    store._snapshots[key] = legacy
    updated = store.save(
        PolicyConfigSnapshot(policy_name="legacy-policy", config={"x": 2}, updated_at=NOW),
        expected_revision=1,
    )
    assert updated.version is not None and updated.version.revision == 1
