from __future__ import annotations

import ast
from pathlib import Path

from application.business_service.projector import CANON_BUSINESS_SERVICE_PROJECTOR
from application.business_service.registry import CANON_BUSINESS_SERVICE_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/business_service/registry.py")
FACTS = Path("application/business_service/facts.py")
FACT_TYPES = {"business_service.created", "business_service.updated", "business_service.archived"}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_service_inventory_names_one_business_service_owner() -> None:
    row = ontology_ownership_by_entity()["Service"]
    assert CANON_BUSINESS_SERVICE_LIFECYCLE_OWNER is True
    assert CANON_BUSINESS_SERVICE_PROJECTOR is True
    assert row.authoritative_module == "contracts.business_service"
    assert row.allowed_writers == ("application.business_service.registry",)
    assert row.allowed_readers == ("application.business_service.projector",)


def test_business_service_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_BUSINESS_SERVICE_LIFECYCLE_OWNER"
                for target in node.targets
            ):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_business_service_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_business_service_registry_delegates_durable_mutation() -> None:
    source = (ROOT / REGISTRY).read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    assert "BusinessFactV1(" not in source
    assert "build_idempotency_key(" not in source


def test_business_autonomy_bootstrap_wires_business_service_owner() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    assert "BusinessServiceRegistry(event_store=customer_event_store, idempotency_store=distributed['idempotency'])" in bootstrap
    assert "service._business_service_registry = business_service_registry" in bootstrap
