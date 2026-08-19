from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from governance.persistence_codec import to_jsonable
from scripts.server.migrate_legacy_tenancy_state import migrate_legacy_tenancy_state
from tenancy.tenant_contract import TenantRecord
from tenancy.tenant_policy_store import build_default_tenant_policy_bundle


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _record(tenant_id: str, *, marker: str = "") -> dict[str, object]:
    payload = to_jsonable(TenantRecord(tenant_id=tenant_id, display_name=tenant_id))
    if marker:
        payload["metadata"] = {"marker": marker}
    return payload


def _policy(tenant_id: str) -> dict[str, object]:
    return to_jsonable(build_default_tenant_policy_bundle(tenant_id))


def test_migration_adds_only_missing_legacy_tenants_and_preserves_runtime_authority(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    runtime = tmp_path / "runtime"
    _write(
        legacy / "tenant_registry.json",
        {"records": [_record("tenant-live", marker="legacy"), _record("tenant-1")]},
    )
    _write(
        legacy / "tenant_policies.json",
        {"bundles": [_policy("tenant-live"), _policy("tenant-1")]},
    )
    _write(
        runtime / "tenant_registry.json",
        {"records": [_record("tenant-live", marker="runtime"), _record("businessaios")]},
    )
    _write(
        runtime / "tenant_policies.json",
        {"bundles": [_policy("businessaios")]},
    )
    legacy_registry_before = (legacy / "tenant_registry.json").read_bytes()
    legacy_policies_before = (legacy / "tenant_policies.json").read_bytes()

    result = migrate_legacy_tenancy_state(legacy_dir=legacy, runtime_dir=runtime)

    assert result.registry_added == ("tenant-1",)
    assert result.policies_added == ("tenant-live", "tenant-1")
    registry_path = runtime / "tenant_registry.json"
    policies_path = runtime / "tenant_policies.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    policies = json.loads(policies_path.read_text(encoding="utf-8"))
    records = {item["tenant_id"]: item for item in registry["records"]}
    bundles = {item["tenant_id"]: item for item in policies["bundles"]}
    assert set(records) == {"businessaios", "tenant-1", "tenant-live"}
    assert records["tenant-live"]["metadata"] == {"marker": "runtime"}
    assert set(bundles) == {"businessaios", "tenant-1", "tenant-live"}
    assert registry_path.stat().st_mode & 0o777 == 0o640
    assert policies_path.stat().st_mode & 0o777 == 0o640
    assert (legacy / "tenant_registry.json").read_bytes() == legacy_registry_before
    assert (legacy / "tenant_policies.json").read_bytes() == legacy_policies_before


def test_migration_check_mode_reports_plan_without_writing(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    runtime = tmp_path / "runtime"
    _write(legacy / "tenant_registry.json", {"records": [_record("tenant-live")]})
    _write(legacy / "tenant_policies.json", {"bundles": [_policy("tenant-live")]})

    result = migrate_legacy_tenancy_state(
        legacy_dir=legacy,
        runtime_dir=runtime,
        write=False,
    )

    assert result.registry_added == ("tenant-live",)
    assert result.policies_added == ("tenant-live",)
    assert not runtime.exists()


def test_migration_rejects_duplicate_tenant_ids_without_mutating_runtime(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    runtime = tmp_path / "runtime"
    duplicate = _record("tenant-live")
    _write(legacy / "tenant_registry.json", {"records": [duplicate, duplicate]})
    _write(legacy / "tenant_policies.json", {"bundles": [_policy("tenant-live")]})
    _write(runtime / "tenant_registry.json", {"records": [_record("businessaios")]})
    _write(runtime / "tenant_policies.json", {"bundles": [_policy("businessaios")]})
    before_registry = (runtime / "tenant_registry.json").read_bytes()
    before_policies = (runtime / "tenant_policies.json").read_bytes()

    with pytest.raises(RuntimeError, match="duplicate tenant_id"):
        migrate_legacy_tenancy_state(legacy_dir=legacy, runtime_dir=runtime)

    assert (runtime / "tenant_registry.json").read_bytes() == before_registry
    assert (runtime / "tenant_policies.json").read_bytes() == before_policies


def test_invalid_policy_blocks_registry_write_before_any_mutation(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    runtime = tmp_path / "runtime"
    _write(legacy / "tenant_registry.json", {"records": [_record("tenant-live")]})
    invalid_policy = _policy("tenant-live")
    invalid_policy["tenant_id"] = ""
    _write(legacy / "tenant_policies.json", {"bundles": [invalid_policy]})
    _write(runtime / "tenant_registry.json", {"records": [_record("businessaios")]})
    _write(runtime / "tenant_policies.json", {"bundles": [_policy("businessaios")]})
    before_registry = (runtime / "tenant_registry.json").read_bytes()
    before_policies = (runtime / "tenant_policies.json").read_bytes()

    with pytest.raises(RuntimeError, match="missing tenant_id"):
        migrate_legacy_tenancy_state(legacy_dir=legacy, runtime_dir=runtime)

    assert (runtime / "tenant_registry.json").read_bytes() == before_registry
    assert (runtime / "tenant_policies.json").read_bytes() == before_policies


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership contract")
def test_write_rejects_process_that_does_not_own_runtime_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    legacy = tmp_path / "legacy"
    runtime = tmp_path / "runtime"
    _write(legacy / "tenant_registry.json", {"records": [_record("tenant-live")]})
    _write(legacy / "tenant_policies.json", {"bundles": [_policy("tenant-live")]})
    _write(runtime / "tenant_registry.json", {"records": [_record("businessaios")]})
    _write(runtime / "tenant_policies.json", {"bundles": [_policy("businessaios")]})
    before_registry = (runtime / "tenant_registry.json").read_bytes()
    before_policies = (runtime / "tenant_policies.json").read_bytes()
    owner_uid = runtime.stat().st_uid
    monkeypatch.setattr(os, "geteuid", lambda: owner_uid + 1)

    with pytest.raises(PermissionError, match="must run as the runtime directory owner"):
        migrate_legacy_tenancy_state(legacy_dir=legacy, runtime_dir=runtime)

    assert (runtime / "tenant_registry.json").read_bytes() == before_registry
    assert (runtime / "tenant_policies.json").read_bytes() == before_policies
