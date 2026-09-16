from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from core.ai.policy_registry import CANON_POLICY_ENTITY_LIFECYCLE_OWNER, POLICY_RUNTIME_STATE_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("core/ai/policy_registry.py")
BOOT = Path("runtime/boot/phase_policy_registry.py")
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm", "bootstrap")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_policy_inventory_names_durable_owner() -> None:
    row = ontology_ownership_by_entity()["Policy"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "core.ai.policy_registry"
    assert row.storage_owner == "runtime.boot.phase_policy_registry"
    assert row.allowed_writers == ("core.ai.policy_registry",)
    assert POLICY_RUNTIME_STATE_SCHEMA_VERSION == 1
    assert CANON_POLICY_ENTITY_LIFECYCLE_OWNER is True


def test_policy_lifecycle_owner_marker_is_unique() -> None:
    owners: list[Path] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name) and target.id == "CANON_POLICY_ENTITY_LIFECYCLE_OWNER"
                for target in node.targets
            ) and isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert owners == [OWNER]


def test_policy_boot_uses_canonical_data_root_and_restores_after_registration() -> None:
    boot = (ROOT / BOOT).read_text(encoding="utf-8")
    phases = (ROOT / "bootstrap/boot_phases.py").read_text(encoding="utf-8")
    services = (ROOT / "runtime/boot/system_builder_parts/runtime_services.py").read_text(encoding="utf-8")
    assert 'Path(base) / "governance" / POLICY_RUNTIME_STATE_FILENAME' in boot
    assert "PolicyRegistry(runtime_state_store=_PolicyRuntimeStateFileStore" in boot
    assert boot.index("_activate_bootstrap_policy") < boot.index("restore_persisted_runtime_state")
    assert "base=base" in phases
    assert "boot_phase_70_policy_registry" in services and "base=base" in services


def test_policy_file_store_reuses_governance_lock_and_atomic_codec() -> None:
    boot = (ROOT / BOOT).read_text(encoding="utf-8")
    assert "exclusive_file_lock" in boot
    assert "atomic_write_json" in boot
    assert "read_json_or_default" in boot
    assert "POLICY_RUNTIME_STATE_GENERATION_CONFLICT" in boot


def test_policy_registry_persists_every_runtime_mutation_and_not_support_artifact_store() -> None:
    owner = (ROOT / OWNER).read_text(encoding="utf-8")
    assert "self._runtime_state_store.save(" in owner
    assert owner.count("self._persist_unlocked(") >= 3
    assert "restore_persisted_runtime_state" in owner
    assert "runtime.platform.support.storage" not in owner
