from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

import config.versioned_config_store as generic
from config.config_audit import PersistentConfigAuditLog
from config.policy_config_store import (
    PersistentPolicyConfigStore,
    PolicyConfigSnapshot,
    policy_config_audit_log_path,
    policy_config_store_path,
)
from config.runtime_config_store import (
    PersistentRuntimeConfigStore,
    RuntimeConfigSnapshot,
    runtime_config_audit_log_path,
    runtime_config_store_path,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_persistent_stores_round_trip_audit_and_idempotence(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_audit = tmp_path / "policy.audit.jsonl"
    store = PersistentPolicyConfigStore(path=policy_path, audit_log_path=policy_audit)
    stored = store.save(
        PolicyConfigSnapshot(policy_name="pricing", config={"price": 100}, labels={"owner": "ops"}, updated_at=NOW),
        actor="owner",
    )
    assert json.loads(policy_path.read_text())["items"][0]["policy_name"] == "pricing"
    PersistentConfigAuditLog(policy_audit).validate_chain()
    assert len(PersistentConfigAuditLog(policy_audit).read_events()) == 1
    same = store.save(PolicyConfigSnapshot(policy_name="pricing", config={"price": 100}, labels={"owner": "ops"}, updated_at=NOW))
    assert same.version == stored.version
    assert len(PersistentConfigAuditLog(policy_audit).read_events()) == 1
    reloaded = PersistentPolicyConfigStore(path=policy_path, audit_log_path=policy_audit)
    assert reloaded.require(policy_name="pricing") == stored
    assert reloaded.history(policy_name="pricing") == (stored,)

    runtime_path = tmp_path / "runtime.json"
    runtime_audit = tmp_path / "runtime.audit.jsonl"
    runtime = PersistentRuntimeConfigStore(path=runtime_path, audit_log_path=runtime_audit)
    saved_runtime = runtime.save(RuntimeConfigSnapshot(profile_name="api", environment="production", runtime_settings={"workers": 2}, updated_at=NOW))
    assert PersistentRuntimeConfigStore(path=runtime_path, audit_log_path=runtime_audit).require(profile_name="api", environment="prod") == saved_runtime
    PersistentConfigAuditLog(runtime_audit).validate_chain()

def test_persistent_save_rolls_back_file_and_memory_when_audit_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "policy.json"
    audit = tmp_path / "audit.jsonl"
    store = PersistentPolicyConfigStore(path=path, audit_log_path=audit)
    first = store.save(PolicyConfigSnapshot(policy_name="pricing", config={"price": 100}, updated_at=NOW))
    before = path.read_text()
    monkeypatch.setattr(store._audit_log, "append", lambda _event: (_ for _ in ()).throw(OSError("audit down")))
    with pytest.raises(OSError, match="audit down"):
        store.save(PolicyConfigSnapshot(policy_name="pricing", config={"price": 200}, updated_at=NOW))
    assert path.read_text() == before
    assert store.require(policy_name="pricing") == first

def test_persistent_save_surfaces_rollback_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "runtime.json"
    audit = tmp_path / "audit.jsonl"
    store = PersistentRuntimeConfigStore(path=path, audit_log_path=audit)
    store.save(RuntimeConfigSnapshot(profile_name="api", environment="prod", runtime_settings={"workers": 1}, updated_at=NOW))
    real_write = generic.atomic_write_json
    calls = 0

    def flaky_write(target, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("rollback down")
        real_write(target, payload)

    monkeypatch.setattr(generic, "atomic_write_json", flaky_write)
    monkeypatch.setattr(store._audit_log, "append", lambda _event: (_ for _ in ()).throw(OSError("audit down")))
    with pytest.raises(RuntimeError, match="audit failed and persistence rollback failed"):
        store.save(RuntimeConfigSnapshot(profile_name="api", environment="prod", runtime_settings={"workers": 2}, updated_at=NOW))
    assert store.require(profile_name="api", environment="prod").runtime_settings == {"workers": 1}

def test_persistent_loader_fails_closed_on_corrupt_or_ambiguous_state(tmp_path: Path) -> None:
    cases = [
        [],
        {"items": {}},
        {"items": [1]},
        {"items": [{"policy_name": "x"}, {"policy_name": "x"}]},
    ]
    for index, payload in enumerate(cases):
        path = tmp_path / f"bad-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            PersistentPolicyConfigStore(path=path, audit_log_path=tmp_path / f"a-{index}.jsonl")

    wrong_codec_path = tmp_path / "wrong-codec.json"
    wrong_codec_path.write_text(json.dumps({"items": [{}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot codec"):
        generic.PersistentVersionedConfigStore(
            namespace="test",
            snapshot_type=PolicyConfigSnapshot,
            key_for_snapshot=lambda item: item.entity_id(),
            snapshot_from_dict=lambda _row: cast(PolicyConfigSnapshot, object()),
            audit_payload=lambda _item: {},
            path=wrong_codec_path,
            audit_log_path=tmp_path / "wrong.audit",
        )

def test_default_paths_and_explicit_environment_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert policy_config_store_path() == tmp_path / "config" / "policy_config_store.json"
    assert policy_config_audit_log_path() == tmp_path / "config" / "policy_config_audit.jsonl"
    assert runtime_config_store_path() == tmp_path / "config" / "runtime_config_store.json"
    assert runtime_config_audit_log_path() == tmp_path / "config" / "runtime_config_audit.jsonl"

    monkeypatch.setenv("BUSINESAIOS_POLICY_CONFIG_STORE_PATH", str(tmp_path / "p.json"))
    monkeypatch.setenv("BUSINESAIOS_POLICY_CONFIG_AUDIT_LOG_PATH", str(tmp_path / "p.audit"))
    monkeypatch.setenv("BUSINESAIOS_RUNTIME_CONFIG_STORE_PATH", str(tmp_path / "r.json"))
    monkeypatch.setenv("BUSINESAIOS_RUNTIME_CONFIG_AUDIT_LOG_PATH", str(tmp_path / "r.audit"))
    assert policy_config_store_path() == tmp_path / "p.json"
    assert policy_config_audit_log_path() == tmp_path / "p.audit"
    assert runtime_config_store_path() == tmp_path / "r.json"
    assert runtime_config_audit_log_path() == tmp_path / "r.audit"

    string_path_store = generic.PersistentVersionedConfigStore(
        namespace="test",
        snapshot_type=PolicyConfigSnapshot,
        key_for_snapshot=lambda item: item.entity_id(),
        snapshot_from_dict=PolicyConfigSnapshot.from_dict,
        audit_payload=lambda _item: {},
        path=str(tmp_path / "string-path.json"),
        audit_log_path=str(tmp_path / "string-path.audit"),
    )
    assert string_path_store.path == tmp_path / "string-path.json"

    for bad in ("", Path(".")):
        with pytest.raises(ValueError):
            generic.PersistentVersionedConfigStore(
                namespace="test",
                snapshot_type=PolicyConfigSnapshot,
                key_for_snapshot=lambda item: item.entity_id(),
                snapshot_from_dict=PolicyConfigSnapshot.from_dict,
                audit_payload=lambda _item: {},
                path=bad,
                audit_log_path=tmp_path / "audit",
            )
