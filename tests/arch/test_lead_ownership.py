from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.lead.projector import CANON_LEAD_PROJECTOR
from application.lead.registry import CANON_LEAD_LIFECYCLE_OWNER
from application.ontology import CANON_ONTOLOGY_EVENT_FACT_MUTATION
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts.lead import Lead

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/lead/registry.py")
FACTS = Path("application/lead/facts.py")
FACT_TYPES = {"lead.created", "lead.updated", "lead.archived"}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_lead_inventory_names_one_writer_and_projection() -> None:
    row = ontology_ownership_by_entity()["Lead"]
    assert CANON_LEAD_LIFECYCLE_OWNER is True
    assert CANON_LEAD_PROJECTOR is True
    assert CANON_ONTOLOGY_EVENT_FACT_MUTATION is True
    assert row.status is OwnershipAuditStatus.DONE
    assert row.allowed_writers == ("application.lead.registry",)
    assert row.allowed_readers == ("application.lead.projector",)


def test_lead_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_LEAD_LIFECYCLE_OWNER"
                for target in node.targets
            ):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_lead_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_canonical_lead_contract_cannot_accumulate_pii_fields() -> None:
    names = {field.name for field in fields(Lead)}
    forbidden = {"name", "full_name", "email", "phone", "company_name", "address", "username"}
    assert names.isdisjoint(forbidden)


def test_crm_lead_remains_transport_surface_not_lifecycle_owner() -> None:
    crm_contract = (ROOT / "crm/crm_lead_contract.py").read_text(encoding="utf-8")
    provider_store = (ROOT / "crm/providers/common/crm_provider_store.py").read_text(encoding="utf-8")
    assert "CANON_LEAD_LIFECYCLE_OWNER" not in crm_contract
    assert "CANON_LEAD_LIFECYCLE_OWNER" not in provider_store
    assert "provider-scoped" in provider_store


def test_business_autonomy_wires_lead_to_existing_event_store() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "LeadRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_lead_registry"' in wiring
    assert "wire_business_ontology_runtime(" in bootstrap


def test_lead_registry_reuses_shared_transition_writer_without_second_fact_path() -> None:
    source = (ROOT / REGISTRY).read_text(encoding="utf-8")
    assert source.count("append_transition_once(") == 2
    assert "BusinessFactV1" not in source
    assert "append_event(" not in source
