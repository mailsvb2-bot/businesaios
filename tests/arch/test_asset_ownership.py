from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.asset import CANON_ASSET_LIFECYCLE_OWNER, CANON_ASSET_PROJECTOR
from application.ontology import CANON_ONTOLOGY_EVENT_FACT_MUTATION
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts.asset import ASSET_SCHEMA_VERSION, Asset

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("application/asset.py")
FACT_TYPES = {"asset.created", "asset.updated", "asset.archived"}


def _python_files():
    for root_name in ("application", "runtime", "storage", "core", "adapters", "billing", "crm", "products"):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_asset_inventory_names_one_writer_and_projection() -> None:
    row = ontology_ownership_by_entity()["Asset"]
    assert CANON_ASSET_LIFECYCLE_OWNER is True
    assert CANON_ASSET_PROJECTOR is True
    assert CANON_ONTOLOGY_EVENT_FACT_MUTATION is True
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "contracts.asset"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("application.asset",)
    assert row.allowed_readers == ("application.asset",)


def test_asset_lifecycle_owner_and_fact_vocabulary_are_unique() -> None:
    owners: list[Path] = []
    fact_owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "CANON_ASSET_LIFECYCLE_OWNER" for target in node.targets)
                and isinstance(node.value, ast.Constant)
                and node.value.value is True
            ):
                owners.append(path.relative_to(ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                fact_owners.add(path.relative_to(ROOT))
    assert owners == [OWNER]
    assert fact_owners == {OWNER}


def test_asset_contract_is_pii_free_and_versioned() -> None:
    names = {field.name for field in fields(Asset)}
    forbidden = {"name", "email", "phone", "address", "owner_name", "description", "custom_fields"}
    assert names.isdisjoint(forbidden)
    assert "schema_version" in names
    assert ASSET_SCHEMA_VERSION == 1


def test_business_autonomy_wires_asset_to_existing_event_store() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "AssetRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_asset_registry"' in wiring
