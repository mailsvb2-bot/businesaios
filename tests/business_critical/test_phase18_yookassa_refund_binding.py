"""Refund facts must be independently verified before revoking canonical access."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from billing.phase18_commercial_settlement import YooKassaCommercialAuthority


def _authority(*, status="succeeded", payment_id="payment-1", refund_amount="1.00"):
    checkout = SimpleNamespace(
        provider_name="yookassa", external_reference="payment-1",
        order_id="order-1", invoice_id="invoice-1", amount_minor=89000,
        currency="RUB",
    )
    calls = []

    def read_refund(refund_id):
        calls.append(refund_id)
        return {
            "id": refund_id, "payment_id": payment_id, "status": status,
            "amount": {"value": refund_amount, "currency": "RUB"},
        }

    authority = YooKassaCommercialAuthority(
        merchant_id="shop-1", create_payment=lambda **kwargs: None,
        fetch_payment=lambda payment_id: {
            "id": payment_id, "metadata": {
                "tenant_id": "tenant-a", "business_id": "business-a",
                "order_id": "order-1", "invoice_id": "invoice-1",
            }, "amount": {"value": "890.00", "currency": "RUB"},
            "status": "succeeded", "paid": True, "captured_at": "2026-10-14T12:00:00Z",
        },
        checkout_reader=lambda **kwargs: checkout,
        fetch_refund=read_refund,
        refund_reference_reader=lambda **kwargs: "refund-1",
    )
    return authority, calls


def _is_reversed(authority):
    return authority.reversal_reader(
        tenant_id="tenant-a", business_id="business-a",
        order_id="order-1", invoice_id="invoice-1",
    )


@pytest.mark.parametrize("status, expected", [
    ("succeeded", True), ("pending", True), ("canceled", False),
])
def test_verified_refund_state_controls_entitlement(status, expected):
    authority, calls = _authority(status=status)
    assert _is_reversed(authority) is expected
    assert calls == ["refund-1"]


@pytest.mark.parametrize("changes", [
    {"payment_id": "another-payment"},
    {"refund_amount": "891.00"},
    {"refund_amount": "NaN"},
    {"status": "unknown"},
])
def test_refund_mismatch_fails_closed(changes):
    authority, _ = _authority(**changes)
    with pytest.raises(RuntimeError):
        _is_reversed(authority)


def test_reference_without_sealed_verifier_does_not_grant_access():
    authority, _ = _authority()
    object.__setattr__(authority, "fetch_refund", None)
    with pytest.raises(RuntimeError, match="refund_verifier_missing"):
        _is_reversed(authority)
