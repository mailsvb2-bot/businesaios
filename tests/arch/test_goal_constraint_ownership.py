from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.business_constraint import (
    CANON_BUSINESS_CONSTRAINT_LIFECYCLE_OWNER,
    CANON_BUSINESS_CONSTRAINT_PROJECTOR,
)
from application.business_goal import CANON_BUSINESS_GOAL_LIFECYCLE_OWNER, CANON_BUSINESS_GOAL_PROJECTOR
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts.business_constraints import (
    BUSINESS_CONSTRAINT_SCHEMA_VERSION,
    BusinessConstraint,
    ConstraintSeverity,
)
from contracts.business_goal import BUSINESS_GOAL_SCHEMA_VERSION, BusinessGoal

ROOT = Path(__file__).resolve().parents[2]
GOAL_OWNER = Path("application/business_goal.py")
CONSTRAINT_OWNER = Path("application/business_constraint.py")
GOAL_FACTS = {"goal.created", "goal.updated", "goal.completed", "goal.cancelled", "goal.archived"}
CONSTRAINT_FACTS = {"constraint.created", "constraint.updated", "constraint.archived"}


def _production_python_files():
    for root_name in ("application", "runtime", "storage", "core", "adapters", "billing", "crm", "products"):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_goal_and_constraint_inventory_name_single_event_store_owners() -> None:
    rows = ontology_ownership_by_entity()
    goal = rows["Goal"]
    constraint = rows["Constraint"]
    assert CANON_BUSINESS_GOAL_LIFECYCLE_OWNER is True
    assert CANON_BUSINESS_GOAL_PROJECTOR is True
    assert goal.status is OwnershipAuditStatus.DONE
    assert goal.authoritative_module == "contracts.business_goal"
    assert goal.storage_owner == "runtime.platform.event_store"
    assert goal.allowed_writers == ("application.business_goal",)
    assert goal.allowed_readers == ("application.business_goal",)
    assert CANON_BUSINESS_CONSTRAINT_LIFECYCLE_OWNER is True
    assert CANON_BUSINESS_CONSTRAINT_PROJECTOR is True
    assert constraint.status is OwnershipAuditStatus.DONE
    assert constraint.authoritative_module == "contracts.business_constraints"
    assert constraint.storage_owner == "runtime.platform.event_store"
    assert constraint.allowed_writers == ("application.business_constraint",)
    assert constraint.allowed_readers == ("application.business_constraint",)


def test_goal_and_constraint_owner_markers_and_fact_vocabularies_are_unique() -> None:
    goal_owners: list[Path] = []
    constraint_owners: list[Path] = []
    goal_fact_owners: set[Path] = set()
    constraint_fact_owners: set[Path] = set()
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and node.value.value is True:
                names = {target.id for target in node.targets if isinstance(target, ast.Name)}
                if "CANON_BUSINESS_GOAL_LIFECYCLE_OWNER" in names:
                    goal_owners.append(path.relative_to(ROOT))
                if "CANON_BUSINESS_CONSTRAINT_LIFECYCLE_OWNER" in names:
                    constraint_owners.append(path.relative_to(ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in GOAL_FACTS:
                    goal_fact_owners.add(path.relative_to(ROOT))
                if node.value in CONSTRAINT_FACTS:
                    constraint_fact_owners.add(path.relative_to(ROOT))
    assert goal_owners == [GOAL_OWNER]
    assert constraint_owners == [CONSTRAINT_OWNER]
    assert goal_fact_owners == {GOAL_OWNER}
    assert constraint_fact_owners == {CONSTRAINT_OWNER}


def test_goal_and_constraint_contracts_are_pii_free_and_versioned() -> None:
    forbidden = {"name", "email", "phone", "address", "description", "custom_fields"}
    assert {field.name for field in fields(BusinessGoal)}.isdisjoint(forbidden)
    assert {field.name for field in fields(BusinessConstraint)}.isdisjoint(forbidden)
    assert BUSINESS_GOAL_SCHEMA_VERSION == 1
    assert BUSINESS_CONSTRAINT_SCHEMA_VERSION == 1


def test_business_autonomy_uses_canonical_constraint_severity() -> None:
    from application.business_autonomy.contracts import ConstraintSeverity as AutonomySeverity

    assert AutonomySeverity is ConstraintSeverity
    tree = ast.parse((ROOT / "application/business_autonomy/contracts.py").read_text(encoding="utf-8"))
    assert not any(isinstance(node, ast.ClassDef) and node.name == "ConstraintSeverity" for node in tree.body)


def test_business_autonomy_wires_goal_and_constraint_to_existing_event_store() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "BusinessGoalRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert "BusinessConstraintRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_business_goal_registry"' in wiring
    assert '"_business_constraint_registry"' in wiring
