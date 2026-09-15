from __future__ import annotations

import ast
from pathlib import Path

from application.organization.projector import CANON_ORGANIZATION_PROJECTOR
from application.organization.registry import CANON_ORGANIZATION_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/organization/registry.py")
PROJECTOR = Path("application/organization/projector.py")
FACTS = Path("application/organization/facts.py")
FACT_TYPES = {"organization.created", "organization.updated", "organization.archived"}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_organization_inventory_names_one_writer_and_read_projection() -> None:
    row = ontology_ownership_by_entity()["Organization"]
    assert CANON_ORGANIZATION_LIFECYCLE_OWNER is True
    assert CANON_ORGANIZATION_PROJECTOR is True
    assert row.allowed_writers == ("application.organization.registry",)
    assert row.allowed_readers == ("application.organization.projector",)


def test_organization_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == "CANON_ORGANIZATION_LIFECYCLE_OWNER" for target in node.targets):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_organization_fact_vocabulary_stays_inside_owner_and_projection() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_organization_reuses_shared_ontology_mutation_primitive() -> None:
    registry = (ROOT / "application/organization/registry.py").read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in registry
    assert "BusinessFactV1(" not in registry
    assert "build_idempotency_key(" not in registry


def test_business_autonomy_bootstrap_wires_organization_owner_to_existing_event_store() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    assert "OrganizationRegistry(event_store=customer_event_store, idempotency_store=distributed['idempotency'])" in bootstrap
    assert "service._organization_registry = organization_registry" in bootstrap
