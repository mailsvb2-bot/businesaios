from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.deal.projector import CANON_DEAL_PROJECTOR
from application.deal.registry import CANON_DEAL_LIFECYCLE_OWNER
from application.ontology import CANON_ONTOLOGY_EVENT_FACT_MUTATION
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from contracts.deal import Deal

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/deal/registry.py")
FACTS = Path("application/deal/facts.py")
FACT_TYPES = {"deal.created", "deal.updated", "deal.archived"}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_deal_inventory_names_one_writer_and_projection() -> None:
    row = ontology_ownership_by_entity()["Deal"]
    assert CANON_DEAL_LIFECYCLE_OWNER is True
    assert CANON_DEAL_PROJECTOR is True
    assert CANON_ONTOLOGY_EVENT_FACT_MUTATION is True
    assert row.status is OwnershipAuditStatus.DONE
    assert row.allowed_writers == ("application.deal.registry",)
    assert row.allowed_readers == ("application.deal.projector",)


def test_deal_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_DEAL_LIFECYCLE_OWNER"
                for target in node.targets
            ):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_deal_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_canonical_deal_contract_cannot_accumulate_crm_pii_fields() -> None:
    names = {field.name for field in fields(Deal)}
    forbidden = {"title", "contact_id", "owner_id", "custom_fields", "email", "phone", "full_name", "name"}
    assert names.isdisjoint(forbidden)


def test_crm_deal_remains_transport_surface_not_lifecycle_owner() -> None:
    crm_contract = (ROOT / "crm/crm_deal_contract.py").read_text(encoding="utf-8")
    provider_store = (ROOT / "crm/providers/common/crm_provider_store.py").read_text(encoding="utf-8")
    assert "CANON_DEAL_LIFECYCLE_OWNER" not in crm_contract
    assert "CANON_DEAL_LIFECYCLE_OWNER" not in provider_store
    assert "provider-scoped" in provider_store


def test_business_autonomy_wires_deal_to_existing_event_store() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "DealRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_deal_registry"' in wiring
    assert "wire_business_ontology_runtime(" in bootstrap


def test_deal_registry_reuses_shared_transition_writer_without_second_fact_path() -> None:
    source = (ROOT / REGISTRY).read_text(encoding="utf-8")
    assert source.count("append_transition_once(") == 2
    assert "BusinessFactV1" not in source
    assert "append_event(" not in source
