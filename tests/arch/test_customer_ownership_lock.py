from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import ontology_ownership_by_entity
from crm.customer_registry import CANON_CUSTOMER_REGISTRY
from crm.customer_timeline import CANON_CUSTOMER_TIMELINE_PROJECTION

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("crm/customer_registry.py")
TIMELINE = Path("crm/customer_timeline.py")
CUSTOMER_FACT_TYPES = {
    "customer.created",
    "customer.identity.attached",
    "customer.contact.observed",
    "customer.archived",
}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_customer_inventory_matches_canonical_registry_and_projection() -> None:
    row = ontology_ownership_by_entity()["Customer"]
    assert CANON_CUSTOMER_REGISTRY is True
    assert CANON_CUSTOMER_TIMELINE_PROJECTION is True
    assert row.allowed_writers == ("crm.customer_registry",)
    assert row.allowed_readers == ("crm.customer_timeline",)


def test_customer_entity_is_constructed_only_by_canonical_registry() -> None:
    constructors: list[tuple[Path, int]] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Customer":
                constructors.append((path.relative_to(ROOT), node.lineno))
    assert {path for path, _ in constructors} == {REGISTRY}


def test_customer_fact_vocabulary_is_owned_by_registry_and_read_only_timeline() -> None:
    owners: dict[str, set[Path]] = {value: set() for value in CUSTOMER_FACT_TYPES}
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in owners:
                owners[node.value].add(path.relative_to(ROOT))
    assert set().union(*owners.values()) == {REGISTRY, TIMELINE}
    assert all(REGISTRY in paths for paths in owners.values())
