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
    PaymentIdentity,
    PaymentLifecycleStatus,
    payment_lifecycle_status_for_event,
)

ROOT = Path(__file__).resolve().parents[2]


def test_payment_inventory_names_existing_event_store_chronology() -> None:
    row = ontology_ownership_by_entity()["Payment"]
    assert row.status is OwnershipAuditStatus.PARTIAL
    assert row.authoritative_module == "core.payments.contracts"
    assert row.storage_owner == "runtime.platform.event_store"
    assert row.allowed_writers == (
        "runtime._internal.effects_actions.payments.selection",
        "runtime._internal.effects_actions.payments.reconciliation",
    )
    assert row.allowed_readers == ("core.payments.read_model",)


def test_payment_identity_is_pii_free_versioned_and_normalized() -> None:
    identity = PaymentIdentity(
        tenant_id=" tenant-a ",
        product_id=" product-a ",
        order_id=" order-123456 ",
        provider=" YooKassa ",
        external_id=" pay_123456 ",
    )
    assert CANON_PAYMENT_SEMANTIC_CONTRACT is True
    assert PAYMENT_SCHEMA_VERSION == 1
    assert identity.tenant_id == "tenant-a"
    assert identity.product_id == "product-a"
    assert identity.order_id == "order-123456"
    assert identity.provider == "yookassa"
    assert identity.external_id == "pay_123456"
    assert {field.name for field in fields(PaymentIdentity)} == {
        "tenant_id", "product_id", "order_id", "provider", "external_id", "schema_version"
    }


@pytest.mark.parametrize("field", ["tenant_id", "product_id", "order_id", "provider"])
def test_payment_identity_rejects_missing_required_scope(field: str) -> None:
    values = {
        "tenant_id": "tenant-a",
        "product_id": "product-a",
        "order_id": "order-123456",
        "provider": "yookassa",
        "external_id": "pay_123456",
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


def test_runtime_creation_uses_canonical_payment_identity() -> None:
    text = (ROOT / "runtime/_internal/effects_actions/payments/selection.py").read_text(encoding="utf-8")
    assert "from core.payments.contracts import PaymentIdentity" in text
    assert "identity = PaymentIdentity(" in text
    assert '"provider": identity.provider' in text


def test_reconciliation_reuses_canonical_terminal_vocabulary() -> None:
    path = ROOT / "runtime/_internal/effects_actions/payments/reconciliation_support.py"
    text = path.read_text(encoding="utf-8")
    assert "from core.payments.contracts import PAYMENT_TERMINAL_EVENT_TYPES" in text
    assert "TERMINAL_EVENTS = PAYMENT_TERMINAL_EVENT_TYPES" in text


def test_provider_port_does_not_define_second_payment_status_dto() -> None:
    path = ROOT / "core/payments/provider.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not any(isinstance(node, ast.ClassDef) and node.name == "PaymentStatus" for node in tree.body)
