from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from typing import cast

import pytest

import config.policy_config_store as policy_module
import config.runtime_config_store as runtime_module
import config.versioned_config_store as generic
from config.config_versioning import ConfigVersion
from config.policy_config_store import (
    InMemoryPolicyConfigStore,
    PersistentPolicyConfigStore,
    PolicyConfigSnapshot,
)
from config.runtime_config_store import (
    InMemoryRuntimeConfigStore,
    PersistentRuntimeConfigStore,
    RuntimeConfigSnapshot,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _DuplicateItemsMapping(dict):
    def items(self):
        return (("x", 1), ("x", 2))


class _NoOffset(tzinfo):
    def utcoffset(self, _dt):
        return None

    def dst(self, _dt):
        return None


def test_canonical_helpers_reject_ambiguous_or_mutable_input(tmp_path: Path) -> None:
    source = {"tuple": (1, 2), "path": tmp_path / "x", "when": NOW, "nested": [{"ok": True}]}
    snapshot = generic.canonical_config_snapshot(source)
    assert snapshot == {
        "nested": [{"ok": True}],
        "path": str(tmp_path / "x"),
        "tuple": [1, 2],
        "when": NOW.isoformat(),
    }
    source["nested"][0]["ok"] = False
    assert snapshot["nested"] == [{"ok": True}]

    for value in ({"x": {1}}, {"x": frozenset({1})}, {"x": b"x"}, {"x": bytearray(b"x")}, {"x": memoryview(b"x")}, {"x": float("inf")}, {1: "x"}):
        with pytest.raises(ValueError):
            generic.canonical_config_snapshot(value)
    with pytest.raises(ValueError, match="duplicate config mapping key"):
        generic.canonical_config_snapshot(_DuplicateItemsMapping())

    protocol_target = object()
    assert generic.VersionedConfigSnapshot.validate(protocol_target) is None
    assert generic.VersionedConfigSnapshot.normalized(protocol_target) is None
    assert generic.VersionedConfigSnapshot.entity_id(protocol_target) is None
    assert generic.VersionedConfigSnapshot.payload_for_versioning(protocol_target) is None
    assert generic.VersionedConfigSnapshot.with_version(
        protocol_target, version=ConfigVersion(namespace="n", entity_id="e", fingerprint="f", created_at=NOW), updated_at=NOW
    ) is None
    assert generic.VersionedConfigSnapshot.to_dict(protocol_target) is None

    assert generic.canonical_labels({" a ": "x"}) == {"a": "x"}
    for labels in ([], {"": "x"}, {1: "x"}, {"x": 1}, {" a ": "x", "a": "y"}):
        with pytest.raises(ValueError):
            generic.canonical_labels(labels)

    assert generic.require_text("field", " x ") == "x"
    for value in (None, 1, " "):
        with pytest.raises(ValueError):
            generic.require_text("field", value)

    assert generic.require_optional_revision(None) is None
    assert generic.require_optional_revision(2) == 2
    for value in (True, 1.0, "1", 0, -1):
        with pytest.raises(ValueError):
            generic.require_optional_revision(value)

    assert generic.require_reason(" reason ") == "reason"
    with pytest.raises(ValueError):
        generic.require_reason(None)

    generic.require_timezone_aware("when", NOW)
    for value in (datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=_NoOffset()), object()):
        with pytest.raises(ValueError):
            generic.require_timezone_aware("when", value)

def test_policy_snapshot_contract_and_serialization() -> None:
    original = PolicyConfigSnapshot(
        policy_name=" pricing ",
        tenant_id=" tenant-a ",
        scope=" product ",
        config={"price": 100, "nested": {"enabled": True}},
        labels={" owner ": "ops"},
        updated_at=NOW,
    )
    normalized = original.normalized()
    assert normalized.policy_name == "pricing"
    assert normalized.tenant_id == "tenant-a"
    assert normalized.scope == "product"
    assert normalized.entity_id() == "tenant-a:product:pricing"
    assert normalized.payload_for_versioning()["config"] == {"nested": {"enabled": True}, "price": 100}
    assert normalized.with_version(
        version=ConfigVersion(namespace="n", entity_id="e", fingerprint="f", created_at=NOW),
        updated_at=NOW,
    ).version is not None

    payload = normalized.to_dict()
    assert PolicyConfigSnapshot.from_dict(payload).to_dict() == payload
    assert PolicyConfigSnapshot.from_dict({"policy_name": "x", "updated_at": "2026-01-01T00:00:00"}).updated_at.tzinfo is not None
    assert PolicyConfigSnapshot.from_dict({"policy_name": "x"}).updated_at.tzinfo is not None
    assert PolicyConfigSnapshot(policy_name="x", tenant_id="legacy", updated_at=NOW).normalized().tenant_id is None

    invalid = [
        PolicyConfigSnapshot(policy_name="", updated_at=NOW),
        PolicyConfigSnapshot(policy_name="x", scope="", updated_at=NOW),
        PolicyConfigSnapshot(policy_name="x", tenant_id=cast(str, 1), updated_at=NOW),
        PolicyConfigSnapshot(policy_name="x", updated_at=datetime(2026, 1, 1)),
        PolicyConfigSnapshot(policy_name="x", config={1: "x"}, updated_at=NOW),
        PolicyConfigSnapshot(policy_name="x", labels={"x": cast(str, 1)}, updated_at=NOW),
        PolicyConfigSnapshot(policy_name="x", version=cast(ConfigVersion, object()), updated_at=NOW),
    ]
    for snapshot in invalid:
        with pytest.raises(ValueError):
            snapshot.validate()

    for payload in (
        cast(dict, []),
        {"policy_name": "x", "version": "bad"},
        {"policy_name": "x", "updated_at": 1},
    ):
        with pytest.raises(ValueError):
            PolicyConfigSnapshot.from_dict(payload)

def test_runtime_snapshot_contract_and_environment_aliases() -> None:
    snapshot = RuntimeConfigSnapshot(
        profile_name=" api ",
        environment=" production ",
        tenant_id=" tenant-a ",
        runtime_settings={"workers": 2},
        labels={" tier ": "critical"},
        updated_at=NOW,
    ).normalized()
    assert snapshot.profile_name == "api"
    assert snapshot.environment == "prod"
    assert snapshot.entity_id() == "tenant-a:prod:api"
    payload = snapshot.to_dict()
    assert RuntimeConfigSnapshot.from_dict(payload).to_dict() == payload
    assert RuntimeConfigSnapshot.from_dict({"profile_name": "x", "environment": "local"}).environment == "dev"
    assert RuntimeConfigSnapshot.from_dict({"profile_name": "x", "environment": "stage", "updated_at": "2026-01-01T00:00:00"}).updated_at.tzinfo is not None

    invalid = [
        RuntimeConfigSnapshot(profile_name="", environment="prod", updated_at=NOW),
        RuntimeConfigSnapshot(profile_name="x", environment="", updated_at=NOW),
        RuntimeConfigSnapshot(profile_name="x", environment=cast(str, 1), updated_at=NOW),
        RuntimeConfigSnapshot(profile_name="x", environment="prod", tenant_id=cast(str, 1), updated_at=NOW),
        RuntimeConfigSnapshot(profile_name="x", environment="prod", updated_at=datetime(2026, 1, 1)),
        RuntimeConfigSnapshot(profile_name="x", environment="prod", runtime_settings={"x": float("nan")}, updated_at=NOW),
        RuntimeConfigSnapshot(profile_name="x", environment="prod", version=cast(ConfigVersion, object()), updated_at=NOW),
    ]
    for item in invalid:
        with pytest.raises(ValueError):
            item.validate()

    for payload in (
        cast(dict, []),
        {"profile_name": "x", "environment": "prod", "version": "bad"},
        {"profile_name": "x", "environment": "prod", "updated_at": 1},
    ):
        with pytest.raises(ValueError):
            RuntimeConfigSnapshot.from_dict(payload)

def test_domain_facades_preserve_public_surface_and_cannot_regrow_second_store_owner() -> None:
    assert generic.CANON_VERSIONED_CONFIG_STORE is True
    assert issubclass(InMemoryPolicyConfigStore, generic.InMemoryVersionedConfigStore)
    assert issubclass(PersistentPolicyConfigStore, generic.PersistentVersionedConfigStore)
    assert issubclass(InMemoryRuntimeConfigStore, generic.InMemoryVersionedConfigStore)
    assert issubclass(PersistentRuntimeConfigStore, generic.PersistentVersionedConfigStore)

    assert policy_module.__all__ == [
        "CANON_POLICY_CONFIG_STORE",
        "InMemoryPolicyConfigStore",
        "PersistentPolicyConfigStore",
        "PolicyConfigSnapshot",
        "policy_config_audit_log_path",
        "policy_config_store_path",
    ]
    assert runtime_module.__all__ == [
        "CANON_RUNTIME_CONFIG_STORE",
        "InMemoryRuntimeConfigStore",
        "PersistentRuntimeConfigStore",
        "RuntimeConfigSnapshot",
        "runtime_config_audit_log_path",
        "runtime_config_store_path",
    ]

    for module in (policy_module, runtime_module):
        source = inspect.getsource(module)
        tree = ast.parse(source)
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assigned_self_attributes = {
            target.attr
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
            if isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        }
        assert not {
            "ConfigVersioning",
            "PersistentConfigAuditLog",
            "atomic_write_json",
            "RLock",
        } & imported_names
        assert not {"_snapshots", "_history", "_lock"} & assigned_self_attributes
        assert "_save_snapshot(" in source
        assert "_save_persistent_snapshot(" in source
