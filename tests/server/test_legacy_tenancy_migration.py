import json
import os
from pathlib import Path

import pytest

from governance.persistence_codec import to_jsonable
from scripts.server.migrate_legacy_tenancy_state import migrate_legacy_tenancy_state
from tenancy.tenant_contract import TenantRecord
from tenancy.tenant_policy_store import build_default_tenant_policy_bundle


def _write(path: Path, key: str, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: items}), encoding="utf-8")


def _record(tenant_id: str, marker: str = "") -> dict:
    item = to_jsonable(TenantRecord(tenant_id=tenant_id, display_name=tenant_id))
    if marker:
        item["metadata"] = {"marker": marker}
    return item


def _policy(tenant_id: str) -> dict:
    return to_jsonable(build_default_tenant_policy_bundle(tenant_id))


def _seed(legacy: Path, runtime: Path) -> None:
    _write(legacy / "tenant_registry.json", "records", [_record("tenant-live", "legacy"), _record("tenant-1")])
    _write(legacy / "tenant_policies.json", "bundles", [_policy("tenant-live"), _policy("tenant-1")])
    _write(runtime / "tenant_registry.json", "records", [_record("tenant-live", "runtime"), _record("businessaios")])
    _write(runtime / "tenant_policies.json", "bundles", [_policy("businessaios")])


def test_merge_only_preserves_runtime_authority_and_modes(tmp_path: Path) -> None:
    legacy, runtime = tmp_path / "legacy", tmp_path / "runtime"
    _seed(legacy, runtime)
    legacy_before = {p.name: p.read_bytes() for p in legacy.iterdir()}
    result = migrate_legacy_tenancy_state(legacy_dir=legacy, runtime_dir=runtime)
    registry = json.loads((runtime / "tenant_registry.json").read_text())["records"]
    policies = json.loads((runtime / "tenant_policies.json").read_text())["bundles"]
    records = {item["tenant_id"]: item for item in registry}
    assert result.registry_added == ("tenant-1",)
    assert result.policies_added == ("tenant-live", "tenant-1")
    assert records["tenant-live"]["metadata"] == {"marker": "runtime"}
    assert {item["tenant_id"] for item in policies} == {"businessaios", "tenant-live", "tenant-1"}
    assert all((runtime / name).stat().st_mode & 0o777 == 0o640 for name in legacy_before)
    assert all((legacy / name).read_bytes() == data for name, data in legacy_before.items())


def test_check_and_invalid_input_never_mutate_runtime(tmp_path: Path) -> None:
    legacy, runtime = tmp_path / "legacy", tmp_path / "runtime"
    _write(legacy / "tenant_registry.json", "records", [_record("tenant-live")])
    _write(legacy / "tenant_policies.json", "bundles", [_policy("tenant-live")])
    result = migrate_legacy_tenancy_state(legacy_dir=legacy, runtime_dir=runtime, write=False)
    assert result.registry_added == result.policies_added == ("tenant-live",)
    assert not runtime.exists()
    _write(runtime / "tenant_registry.json", "records", [_record("businessaios")])
    _write(runtime / "tenant_policies.json", "bundles", [_policy("businessaios")])
    before = {p.name: p.read_bytes() for p in runtime.iterdir()}
    bad = _policy("tenant-live")
    bad["tenant_id"] = ""
    _write(legacy / "tenant_policies.json", "bundles", [bad])
    with pytest.raises(RuntimeError, match="missing tenant_id"):
        migrate_legacy_tenancy_state(legacy_dir=legacy, runtime_dir=runtime)
    assert all((runtime / name).read_bytes() == data for name, data in before.items())


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership contract")
def test_write_rejects_foreign_runtime_owner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    legacy, runtime = tmp_path / "legacy", tmp_path / "runtime"
    _seed(legacy, runtime)
    before = {p.name: p.read_bytes() for p in runtime.iterdir()}
    monkeypatch.setattr(os, "geteuid", lambda: runtime.stat().st_uid + 1)
    with pytest.raises(PermissionError, match="runtime directory owner"):
        migrate_legacy_tenancy_state(legacy_dir=legacy, runtime_dir=runtime)
    assert all((runtime / name).read_bytes() == data for name, data in before.items())
