from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import ontology_ownership_by_entity
from core.ai.policy_registry import CANON_POLICY_ENTITY_LIFECYCLE_OWNER

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
OWNER = Path("core/ai/policy_registry.py")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_policy_inventory_names_single_runtime_entity_owner() -> None:
    row = ontology_ownership_by_entity()["Policy"]
    assert row.status.value == "done"
    assert row.authoritative_module == "core.ai.policy_registry"
    assert row.allowed_writers == ("core.ai.policy_registry",)
    assert row.allowed_readers == ("core.policies.selector",)
    assert row.storage_owner == "runtime.boot.phase_policy_registry"


def test_policy_runtime_lifecycle_owner_marker_is_unique() -> None:
    owners: list[Path] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == "CANON_POLICY_ENTITY_LIFECYCLE_OWNER" for target in node.targets):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert CANON_POLICY_ENTITY_LIFECYCLE_OWNER is True
    assert owners == [OWNER]


def test_canonical_policy_registry_never_hardcodes_v1_refs() -> None:
    text = (ROOT / OWNER).read_text(encoding="utf-8")
    assert 'version="v1"' not in text
    assert "POLICY_ID_MUST_BE_VERSIONED" in text
    assert "POLICY_SNAPSHOT_VERSION_MISMATCH" in text
    assert "POLICY_RUNTIME_STATE_SCHEMA_VERSION" in text
    assert "expected_generation" in text


def test_only_boot_constructs_canonical_policy_registry_in_production() -> None:
    constructors: list[Path] = []
    for path in _python_files():
        if path.relative_to(ROOT) == OWNER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "PolicyRegistry"
            for node in ast.walk(tree)
        ):
            constructors.append(path.relative_to(ROOT))
    assert constructors == [Path("runtime/boot/phase_policy_registry.py")]
