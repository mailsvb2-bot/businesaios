from __future__ import annotations

import ast
from pathlib import Path

from application.opportunity import CANON_OPPORTUNITY_LIFECYCLE_OWNER, CANON_OPPORTUNITY_PROJECTOR
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
OWNER = Path("application/opportunity.py")
FACT_TYPES = {"opportunity.created", "opportunity.updated", "opportunity.archived"}


def _python_files():
    for root_name in ("application", "runtime", "storage", "core", "adapters", "billing", "crm", "ml"):
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_opportunity_inventory_names_one_writer_and_projection() -> None:
    row = ontology_ownership_by_entity()["Opportunity"]
    assert CANON_OPPORTUNITY_LIFECYCLE_OWNER is True
    assert CANON_OPPORTUNITY_PROJECTOR is True
    assert row.status is OwnershipAuditStatus.DONE
    assert row.allowed_writers == ("application.opportunity",)
    assert row.allowed_readers == ("application.opportunity",)


def test_opportunity_lifecycle_owner_and_fact_vocabulary_are_unique() -> None:
    owners: list[Path] = []
    fact_owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_OPPORTUNITY_LIFECYCLE_OWNER"
                for target in node.targets
            ) and isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                fact_owners.add(path.relative_to(ROOT))
    assert owners == [OWNER]
    assert fact_owners == {OWNER}


def test_scoring_and_discovery_opportunities_remain_projections() -> None:
    for relative in (
        "application/process_discovery/contracts.py",
        "core/growth/strategy/contracts.py",
        "ml/explainability/opportunity_explainer.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "CANON_OPPORTUNITY_LIFECYCLE_OWNER" not in text


def test_business_autonomy_wires_opportunity_to_existing_event_store() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "OpportunityRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_opportunity_registry"' in wiring
