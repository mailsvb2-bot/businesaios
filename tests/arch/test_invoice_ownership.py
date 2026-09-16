from __future__ import annotations

import ast
from pathlib import Path

from billing.invoice_registry import (
    CANON_BILLING_INVOICE_LIFECYCLE_OWNER,
    CANON_BILLING_INVOICE_PROJECTOR,
    INVOICE_FACT_TYPES,
    INVOICE_SCHEMA_VERSION,
)
from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm")
OWNER = Path("billing/invoice_registry.py")


def _python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_invoice_inventory_names_one_durable_owner() -> None:
    row = ontology_ownership_by_entity()["Invoice"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "billing.invoice_lifecycle"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == ("billing.invoice_registry",)
    assert row.allowed_readers == ("billing.invoice_registry",)
    assert "single durable lifecycle writer" in row.reason
    assert INVOICE_SCHEMA_VERSION == 1


def test_invoice_lifecycle_owner_marker_is_unique() -> None:
    owners: list[Path] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name)
                and target.id == "CANON_BILLING_INVOICE_LIFECYCLE_OWNER"
                for target in node.targets
            ) and isinstance(node.value, ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert owners == [OWNER]
    assert CANON_BILLING_INVOICE_LIFECYCLE_OWNER is True
    assert CANON_BILLING_INVOICE_PROJECTOR is True


def test_invoice_fact_vocabulary_has_one_owner() -> None:
    owners: set[Path] = set()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in INVOICE_FACT_TYPES:
                    owners.add(path.relative_to(ROOT))
    assert owners == {OWNER}


def test_invoice_registry_uses_shared_event_fact_mutation() -> None:
    source = (ROOT / OWNER).read_text(encoding="utf-8")
    assert "EventFactLifecycleWriter" in source
    assert 'namespace="invoice_fact"' in source
    assert 'source="invoice_registry"' in source
    assert "BusinessFactV1(" not in source


def test_business_ontology_runtime_wires_invoice_registry_to_existing_stores() -> None:
    wiring = (ROOT / "runtime/business_autonomy/ontology_runtime.py").read_text(encoding="utf-8")
    assert "InvoiceRegistry(event_store=event_store, idempotency_store=idempotency_store)" in wiring
    assert '"_invoice_registry"' in wiring


def test_billing_public_surface_exports_invoice_registry_without_second_invoice_model() -> None:
    package = (ROOT / "billing/__init__.py").read_text(encoding="utf-8")
    assert "from billing.invoice_registry import InvoiceRegistry" in package
    assert "'InvoiceRegistry'" in package
    assert "class CommercialInvoiceEnvelope" not in (ROOT / OWNER).read_text(encoding="utf-8")


def test_detached_invoice_transforms_preserve_business_scope_without_owning_storage() -> None:
    refund = (ROOT / "billing/refund_orchestrator.py").read_text(encoding="utf-8")
    chargeback = (ROOT / "billing/chargeback_orchestrator.py").read_text(encoding="utf-8")
    click_preview = (ROOT / "click_economics/public_api_billing.py").read_text(encoding="utf-8")
    assert refund.count("business_id=invoice.business_id") == refund.count("CommercialInvoiceEnvelope(")
    assert chargeback.count("business_id=invoice.business_id") == chargeback.count("CommercialInvoiceEnvelope(")
    assert "business_id=record.business_id" in click_preview
    assert "business_id=invoice_preview.business_id" in click_preview
    assert "CANON_BILLING_INVOICE_LIFECYCLE_OWNER" not in refund
    assert "CANON_BILLING_INVOICE_LIFECYCLE_OWNER" not in chargeback
    assert "CANON_BILLING_INVOICE_LIFECYCLE_OWNER" not in click_preview
