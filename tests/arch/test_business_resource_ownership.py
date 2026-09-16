from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.business_resource import (
    CANON_BUSINESS_RESOURCE_LIFECYCLE_OWNER,
    CANON_BUSINESS_RESOURCE_PROJECTOR,
)
from application.ontology import CANON_ONTOLOGY_EVENT_FACT_MUTATION
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts.business_resource import BUSINESS_RESOURCE_SCHEMA_VERSION, BusinessResource

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("application/business_resource.py")
FACT_TYPES = {"resource.created", "resource.updated", "resource.archived"}


def _python_files():
    for root_name in ("application", "runtime", "storage", "core", "adapters", "billing", "crm", "products"):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_resource_inventory_names_one_business_owner() -> None:
    row = ontology_ownership_by_entity()["Resource"]
    assert CANON_BUSINESS_RESOURCE_LIFECYCLE_OWNER is True
    assert CANON_BUSINESS_RESOURCE_PROJECTOR is True
    assert CANON_ONTOLOGY_EVENT_FACT_MUTATION is True
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "contracts.business_resource"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("application.business_resource",)
    assert row.allowed_readers == ("application.business_resource",)


def test_business_resource_lifecycle_owner_and_fact_vocabulary_are_unique() -> None:
    owners: list[Path] = []
    fact_owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "CANON_BUSINESS_RESOURCE_LIFECYCLE_OWNER"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Constant)
                and node.value.value is True
            ):
                owners.append(path.relative_to(ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                fact_owners.add(path.relative_to(ROOT))
    assert owners == [OWNER]
    assert fact_owners == {OWNER}


def test_business_resource_contract_is_pii_free_and_versioned() -> None:
    names = {field.name for field in fields(BusinessResource)}
    forbidden = {"name", "email", "phone", "address", "owner_name", "description", "custom_fields"}
    assert names.isdisjoint(forbidden)
    assert "schema_version" in names
    assert BUSINESS_RESOURCE_SCHEMA_VERSION == 1


def test_technical_resource_surfaces_are_not_business_lifecycle_owners() -> None:
    paths = (
        ROOT / "runtime/platform/support/optimization/search/__init__.py",
        ROOT / "runtime/business_autonomy/provider_response_parsers.py",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "CANON_BUSINESS_RESOURCE_LIFECYCLE_OWNER" not in text


def test_business_autonomy_wires_resource_to_existing_event_store() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "BusinessResourceRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_business_resource_registry"' in wiring
