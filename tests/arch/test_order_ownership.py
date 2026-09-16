from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts.order import CANON_ORDER_CONTRACT, Order
from lead_outcomes.client_outcome_order_store import (
    CANON_ORDER_LIFECYCLE_OWNER,
    ClientOutcomeOrderStore,
    OrderStore,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = (
    "application",
    "runtime",
    "storage",
    "core",
    "adapters",
    "billing",
    "crm",
    "lead_outcomes",
)
OWNER = Path("lead_outcomes/client_outcome_order_store.py")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_order_inventory_names_one_owner_and_storage() -> None:
    row = ontology_ownership_by_entity()["Order"]
    assert CANON_ORDER_CONTRACT is True
    assert CANON_ORDER_LIFECYCLE_OWNER is True
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "contracts.order"
    assert row.storage_owner == "runtime.platform.client_outcome_persistence"
    assert row.allowed_writers == ("lead_outcomes.client_outcome_order_store",)
    assert row.allowed_readers == ("lead_outcomes.client_outcome_order_store",)


def test_order_lifecycle_owner_marker_is_unique() -> None:
    owners: list[Path] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name)
                and target.id == "CANON_ORDER_LIFECYCLE_OWNER"
                for target in node.targets
            ):
                continue
            if isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert owners == [OWNER]


def test_order_contract_cannot_accumulate_pii_fields() -> None:
    names = {field.name for field in fields(Order)}
    forbidden = {
        "name",
        "display_name",
        "email",
        "phone",
        "username",
        "address",
        "external_subject",
    }
    assert names.isdisjoint(forbidden)


def test_client_outcome_store_is_compatibility_alias_of_canonical_order_store() -> None:
    assert ClientOutcomeOrderStore is OrderStore


def test_client_outcome_runtime_wires_canonical_and_legacy_namespaces() -> None:
    wiring = (ROOT / "entrypoints/api/client_outcome_route_handlers.py").read_text(
        encoding="utf-8"
    )
    assert "backend=persistence.registry('order')" in wiring
    assert "legacy_backend=persistence.registry('client_outcome_order')" in wiring


def test_legacy_backend_is_read_only_migration_source() -> None:
    source = (ROOT / OWNER).read_text(encoding="utf-8")
    assert "self._legacy_backend.items()" in source
    assert "self._legacy_backend.replace(" not in source
    assert "self._legacy_backend.register" not in source
