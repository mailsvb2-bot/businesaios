from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.ontology import CANON_ONTOLOGY_EVENT_FACT_MUTATION
from application.person.projector import CANON_PERSON_PROJECTOR
from application.person.registry import CANON_PERSON_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity
from contracts.person import Person

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/person/registry.py")
FACTS = Path("application/person/projector.py")
FACT_TYPES = {"person.created", "person.archived"}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_person_inventory_names_one_writer_and_projection() -> None:
    row = ontology_ownership_by_entity()["Person"]
    assert CANON_PERSON_LIFECYCLE_OWNER is True
    assert CANON_PERSON_PROJECTOR is True
    assert CANON_ONTOLOGY_EVENT_FACT_MUTATION is True
    assert row.allowed_writers == ("application.person.registry",)
    assert row.allowed_readers == ("application.person.projector",)


def test_person_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "CANON_PERSON_LIFECYCLE_OWNER" for target in node.targets):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_person_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_person_contract_cannot_accumulate_pii_fields() -> None:
    names = {field.name for field in fields(Person)}
    forbidden = {"name", "display_name", "email", "phone", "username", "external_subject", "address"}
    assert names.isdisjoint(forbidden)


def test_behavior_person_snapshot_is_not_lifecycle_owner() -> None:
    repository = (ROOT / "core/behavior/persistence/person_snapshot_repository.py").read_text(encoding="utf-8")
    assert "CANON_PERSON_LIFECYCLE_OWNER" not in repository
    assert "contracts.person" not in repository


def test_business_autonomy_bootstrap_wires_person_to_existing_event_store() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "PersonRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_person_registry"' in wiring
    assert "wire_business_ontology_runtime(" in bootstrap
