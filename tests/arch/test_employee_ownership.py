from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.employee.projector import CANON_EMPLOYEE_PROJECTOR
from application.employee.registry import CANON_EMPLOYEE_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity
from contracts.employee import Employee

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/employee/registry.py")
FACTS = Path("application/employee/facts.py")
FACT_TYPES = {"employee.created", "employee.archived"}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_employee_inventory_names_one_writer_and_projection() -> None:
    row = ontology_ownership_by_entity()["Employee"]
    assert CANON_EMPLOYEE_LIFECYCLE_OWNER is True
    assert CANON_EMPLOYEE_PROJECTOR is True
    assert row.allowed_writers == ("application.employee.registry",)
    assert row.allowed_readers == ("application.employee.projector",)


def test_employee_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_EMPLOYEE_LIFECYCLE_OWNER"
                for target in node.targets
            ):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_employee_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_employee_contract_cannot_accumulate_pii_fields() -> None:
    names = {field.name for field in fields(Employee)}
    forbidden = {"name", "display_name", "email", "phone", "username", "external_subject", "address"}
    assert names.isdisjoint(forbidden)


def test_employee_registry_delegates_durable_mutation_and_validates_relations() -> None:
    source = (ROOT / REGISTRY).read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    assert "PersonProjector" in source
    assert "OrganizationProjector" in source
    assert "BusinessFactV1(" not in source
    assert "build_idempotency_key(" not in source


def test_business_autonomy_bootstrap_wires_employee_to_existing_event_store() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "EmployeeRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_employee_registry"' in wiring
    assert "wire_business_ontology_runtime(" in bootstrap
