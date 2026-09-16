from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from runtime.business_autonomy.provider_activation_store import CANON_PROVIDER_ACTIVATION_STORE

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
CATALOG = Path("application/business_autonomy/provider_catalog.py")
STORE = Path("runtime/business_autonomy/provider_activation_store.py")
WRITER = Path("application/business_autonomy/provider_admin_service.py")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_provider_inventory_names_existing_single_owners() -> None:
    row = ontology_ownership_by_entity()["Provider"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "application.business_autonomy.provider_catalog"
    assert row.storage_owner == "runtime.business_autonomy.provider_activation_store"
    assert row.allowed_writers == ("application.business_autonomy.provider_admin_service",)
    assert row.allowed_readers == ("application.business_autonomy.provider_admin_service",)
    assert CANON_PROVIDER_ACTIVATION_STORE is True


def test_provider_definitions_are_constructed_only_by_canonical_catalog() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ProviderDefinition":
                owners.add(path.relative_to(ROOT))
    assert owners == {CATALOG}


def test_provider_activation_collection_has_one_owner() -> None:
    owners = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        if "provider_activation_state" in text:
            owners.append(path.relative_to(ROOT))
    assert owners == [STORE]


def test_provider_activation_writes_are_owned_by_admin_service() -> None:
    writers = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        if "activation_store.put(" in text:
            writers.append(path.relative_to(ROOT))
    assert writers == [WRITER]


def test_provider_activation_store_validates_scope_on_write_and_readback() -> None:
    source = (ROOT / STORE).read_text(encoding="utf-8")
    assert "status.validate_scope()" in source
    assert 'raise ValueError("business_id is required")' in source
    assert 'raise ValueError("provider_key is required")' in source
