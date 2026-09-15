from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from application.partner.projector import CANON_PARTNER_PROJECTOR
from application.partner.registry import CANON_PARTNER_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity
from contracts.partner import Partner

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
REGISTRY = Path("application/partner/registry.py")
FACTS = Path("application/partner/facts.py")
FACT_TYPES = {"partner.created", "partner.archived"}


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_partner_inventory_names_one_writer_and_projection() -> None:
    row = ontology_ownership_by_entity()["Partner"]
    assert CANON_PARTNER_LIFECYCLE_OWNER is True
    assert CANON_PARTNER_PROJECTOR is True
    assert row.allowed_writers == ("application.partner.registry",)
    assert row.allowed_readers == ("application.partner.projector",)


def test_partner_lifecycle_owner_marker_is_unique() -> None:
    owners = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CANON_PARTNER_LIFECYCLE_OWNER"
                for target in node.targets
            ):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    owners.append(path.relative_to(ROOT))
    assert owners == [REGISTRY]


def test_partner_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners == {FACTS}


def test_partner_contract_cannot_accumulate_pii_fields() -> None:
    names = {field.name for field in fields(Partner)}
    forbidden = {"name", "display_name", "email", "phone", "username", "external_subject", "address"}
    assert names.isdisjoint(forbidden)


def test_partner_registry_uses_canonical_party_projectors_and_shared_writer() -> None:
    source = (ROOT / REGISTRY).read_text(encoding="utf-8")
    assert "PersonProjector" in source
    assert "OrganizationProjector" in source
    assert "EventFactLifecycleWriter" in source
    assert "BusinessFactV1(" not in source
    assert "build_idempotency_key(" not in source


def test_business_autonomy_bootstrap_wires_partner_to_existing_event_store() -> None:
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "PartnerRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_partner_registry"' in wiring
    assert "wire_business_ontology_runtime(" in bootstrap
