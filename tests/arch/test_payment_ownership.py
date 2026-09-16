from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from core.events.event_types import (
    PAYMENT_CAPTURED,
    PAYMENT_CHECKED,
    PAYMENT_CREATED,
    PAYMENT_FAILED,
    PAYMENT_SUCCEEDED,
)
from core.payments.contracts import (
    CANON_PAYMENT_SEMANTIC_CONTRACT,
    PAYMENT_SCHEMA_VERSION,
    PAYMENT_TERMINAL_EVENT_TYPES,
    Payment,
    PaymentIdentity,
    PaymentLifecycleStatus,
    payment_lifecycle_status_for_event,
)
from core.payments.read_model import CANON_PAYMENT_PROJECTOR, PaymentProjector

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "runtime", "storage", "core", "adapters", "billing", "crm", "contracts")


def _definitions(class_name: str) -> list[Path]:
    found: list[Path] = []
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(isinstance(node, ast.ClassDef) and node.name == class_name for node in tree.body):
                found.append(path.relative_to(ROOT))
    return sorted(found)


def test_payment_inventory_names_existing_event_store_chronology() -> None:
    row = ontology_ownership_by_entity()["Payment"]
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "core.payments.contracts"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == (
        "runtime._internal.effects_actions.payments.selection",
        "runtime._internal.effects_actions.payments.reconciliation",
    )
    assert row.allowed_readers == ("core.payments.read_model",)


def test_payment_identity_is_pii_free_versioned_and_normalized() -> None:
    identity = PaymentIdentity(
        tenant_id=" tenant-a ", business_id=" business-a ", product_id=" product-a ",
        order_id=" order-123456 ", provider=" YooKassa ", external_id=" pay_123456 ",
    )
    assert CANON_PAYMENT_SEMANTIC_CONTRACT is True
    assert PAYMENT_SCHEMA_VERSION == 2
    assert identity.tenant_id == "tenant-a"
    assert identity.business_id == "business-a"
    assert identity.product_id == "product-a"
    assert identity.order_id == "order-123456"
    assert identity.provider == "yookassa"
    assert identity.external_id == "pay_123456"
    assert {field.name for field in fields(PaymentIdentity)} == {
        "tenant_id", "business_id", "product_id", "order_id", "provider", "external_id", "schema_version"
    }


@pytest.mark.parametrize("field", ["tenant_id", "business_id", "product_id", "order_id", "provider"])
def test_payment_identity_rejects_missing_required_scope(field: str) -> None:
    values = {
        "tenant_id": "tenant-a", "business_id": "business-a", "product_id": "product-a",
        "order_id": "order-123456", "provider": "yookassa", "external_id": "pay_123456",
    }
    values[field] = ""
    with pytest.raises(ValueError):
        PaymentIdentity(**values)


def test_payment_lifecycle_vocabulary_reuses_canonical_event_types() -> None:
    assert payment_lifecycle_status_for_event(PAYMENT_CREATED) is PaymentLifecycleStatus.CREATED
    assert payment_lifecycle_status_for_event(PAYMENT_CHECKED) is PaymentLifecycleStatus.CHECKED
    assert payment_lifecycle_status_for_event(PAYMENT_SUCCEEDED) is PaymentLifecycleStatus.SUCCEEDED
    assert payment_lifecycle_status_for_event(PAYMENT_CAPTURED) is PaymentLifecycleStatus.SUCCEEDED
    assert payment_lifecycle_status_for_event(PAYMENT_FAILED) is PaymentLifecycleStatus.FAILED
    assert PAYMENT_TERMINAL_EVENT_TYPES == frozenset({PAYMENT_CAPTURED, PAYMENT_FAILED})
    with pytest.raises(ValueError):
        payment_lifecycle_status_for_event("provider_unknown")


def test_payment_entity_and_projector_have_single_canonical_definitions() -> None:
    assert _definitions("Payment") == [Path("core/payments/contracts.py")]
    assert CANON_PAYMENT_PROJECTOR is True
    assert PaymentProjector.__module__ == "core.payments.read_model"
    assert "identity" in Payment.__dataclass_fields__
    assert "amount_minor" in Payment.__dataclass_fields__
    assert "currency" in Payment.__dataclass_fields__


def test_runtime_creation_uses_canonical_payment_identity_and_v2_marker() -> None:
    text = (ROOT / "runtime/_internal/effects_actions/payments/selection.py").read_text(encoding="utf-8")
    assert "from core.payments.contracts import PAYMENT_SCHEMA_VERSION, PaymentIdentity" in text
    assert "identity = PaymentIdentity(" in text
    assert 'business_id=causal_metadata["business_id"]' in text
    assert '"schema_version": PAYMENT_SCHEMA_VERSION' in text
    assert '"provider": identity.provider' in text


def test_reconciliation_reuses_canonical_terminal_vocabulary_and_v2_marker() -> None:
    support = (ROOT / "runtime/_internal/effects_actions/payments/reconciliation_support.py").read_text(encoding="utf-8")
    runtime = (ROOT / "runtime/_internal/effects_actions/payments/reconciliation.py").read_text(encoding="utf-8")
    assert "from core.payments.contracts import PAYMENT_TERMINAL_EVENT_TYPES" in support
    assert "TERMINAL_EVENTS = PAYMENT_TERMINAL_EVENT_TYPES" in support
    assert "from core.payments.contracts import PAYMENT_SCHEMA_VERSION" in runtime
    assert runtime.count('"schema_version": PAYMENT_SCHEMA_VERSION') >= 4


def test_provider_port_does_not_define_second_payment_status_dto() -> None:
    path = ROOT / "core/payments/provider.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not any(isinstance(node, ast.ClassDef) and node.name == "PaymentStatus" for node in tree.body)


def test_payment_runtime_requires_and_propagates_business_scope() -> None:
    selection = (ROOT / "runtime/_internal/effects_actions/payments/selection.py").read_text(encoding="utf-8")
    reconciliation = (ROOT / "runtime/_internal/effects_actions/payments/reconciliation.py").read_text(encoding="utf-8")
    handler = (ROOT / "runtime/handler_impl/domains/payment_ops.py").read_text(encoding="utf-8")
    catalog = (ROOT / "core/actions/catalog_groups.py").read_text(encoding="utf-8")
    assert 'for field in ("tenant_id", "business_id", "product_id", "order_id")' in selection
    assert 'business_id=causal_metadata["business_id"]' in selection
    assert 'PAYMENT_BUSINESS_CONTEXT_MISMATCH' in reconciliation
    assert 'PAYMENT_BUSINESS_SCOPE_REQUIRED' in reconciliation
    assert 'current_execution_business_id()' in handler
    assert 'payment_optional = {"business_id",' in catalog
    assert 'optional={"business_id", "window_min"}' in catalog


def test_legacy_latest_status_remains_compatibility_read_not_projector_truth() -> None:
    text = (ROOT / "core/payments/read_model.py").read_text(encoding="utf-8")
    assert "def latest_payment_status(" in text
    assert "if schema is None:" in text
    assert "Explicitly legacy/non-authoritative chronology" in text
    assert "class PaymentProjector:" in text
