"""One merchant-read authority across checkout, settlement and reversal.

No fake browser 'paid' signal can create invoice money or unlock access.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from billing.phase18_yookassa_authority import YooKassaCommercialAuthority
from billing.payment_provider_contract import PaymentCheckoutRequest


SCOPE = {"tenant_id": "tenant-a", "business_id": "business-a"}


class Merchant:
    def __init__(self):
        self.created = 0
        self.snapshot = {
            "id": "payment-1", "status": "pending", "paid": False,
            "amount": {"value": "890.00", "currency": "RUB"},
            "confirmation": {"confirmation_url": "https://yookassa.ru/checkout/pay-1"},
            "metadata": {"tenant_id": "tenant-a", "business_id": "business-a", "order_id": "order-a",
                         "invoice_id": "invoice-a", "program_id": "program-a"},
        }

    def create(self, **kwargs):
        self.created += 1
        assert kwargs["amount_minor"] == 89000
        assert kwargs["currency"] == "RUB"
        return dict(self.snapshot)

    def fetch(self, payment_id):
        assert payment_id == "payment-1"
        return dict(self.snapshot)


class CheckoutOwner:
    def __init__(self):
        self.row = None

    def __call__(self, **kwargs):
        row = self.row
        if row is None:
            return None
        if any(getattr(row, k) != v for k, v in kwargs.items()):
            return None
        return row


def setup():
    merchant = Merchant()
    owner = CheckoutOwner()
    authority = YooKassaCommercialAuthority(
        merchant_id="merchant-prod", create_payment=merchant.create,
        fetch_payment=merchant.fetch, checkout_reader=owner,
    )
    request = PaymentCheckoutRequest(
        tenant_id="tenant-a", amount_minor=89000, currency="RUB",
        idempotency_key="payment-once", customer_reference="customer-a",
        metadata={k: v for k, v in merchant.snapshot["metadata"].items() if k != "tenant_id"},
    )
    session = authority.create_checkout(request)
    owner.row = type("Checkout", (), dict(
        tenant_id="tenant-a", business_id="business-a",
        order_id="order-a", invoice_id="invoice-a",
        provider_name=session.provider_name,
        external_reference=session.external_reference,
        amount_minor=session.amount_minor, currency=session.currency,
    ))()
    return merchant, owner, authority


def test_full_payment_authority_requires_authenticated_merchant_read_and_current_nonrefunded_payment():
    merchant, owner, authority = setup()
    pending = authority.fetch_settlement_evidence(**SCOPE, provider_name="yookassa", external_reference="payment-1")
    assert pending.status == "pending"
    assert authority.reversal_reader(**SCOPE, order_id="order-a", invoice_id="invoice-a") is True
    merchant.snapshot.update(status="succeeded", paid=True, captured_at="2026-10-13T12:00:00Z")
    proof = authority.fetch_settlement_evidence(**SCOPE, provider_name="yookassa", external_reference="payment-1")
    assert (proof.status, proof.amount_minor, proof.evidence_id) == ("succeeded", 89000, "yookassa:payment:payment-1")
    assert authority.reversal_reader(**SCOPE, order_id="order-a", invoice_id="invoice-a") is False
    merchant.snapshot["refunded_amount"] = {"value": "1.00", "currency": "RUB"}
    assert authority.reversal_reader(**SCOPE, order_id="order-a", invoice_id="invoice-a") is True


@pytest.mark.parametrize("path,value", [
    ("id", "unrelated"),
    ("status", "invented"),
    ("amount", {"value": "890.01", "currency": "RUB"}),
    ("amount", {"value": "NaN", "currency": "RUB"}),
    ("metadata", {"business_id": "business-b", "order_id": "order-a", "invoice_id": "invoice-a"}),
])
def test_wrong_provider_payment_never_settles_or_entitles(path, value):
    merchant, _, authority = setup()
    merchant.snapshot[path] = value
    with pytest.raises(RuntimeError):
        authority.fetch_settlement_evidence(**SCOPE, provider_name="yookassa", external_reference="payment-1")
    with pytest.raises(RuntimeError):
        authority.reversal_reader(**SCOPE, order_id="order-a", invoice_id="invoice-a")


def test_unknown_reversal_authority_fails_closed():
    merchant, _, authority = setup()
    merchant.snapshot.update(status="succeeded", paid=True, captured_at="2026-10-13T12:00:00Z")
    def offline(payment_id):
        raise TimeoutError("merchant unavailable")
    authority = replace(authority, fetch_payment=offline)
    with pytest.raises(TimeoutError):
        authority.reversal_reader(**SCOPE, order_id="order-a", invoice_id="invoice-a")


def test_cross_business_scope_and_untrusted_checkout_fail_closed():
    merchant, owner, authority = setup()
    with pytest.raises(RuntimeError):
        authority.fetch_settlement_evidence(
            tenant_id="tenant-a", business_id="business-b",
            provider_name="yookassa", external_reference="payment-1",
        )
    with pytest.raises(RuntimeError):
        authority.reversal_reader(tenant_id="tenant-a", business_id="business-b",
                                   order_id="order-a", invoice_id="invoice-a")
    merchant.snapshot["paid"] = True
    merchant.snapshot["status"] = "succeeded"
    # No captured_at: a mere status flag is not an authoritative final settlement.
    assert authority.fetch_settlement_evidence(
        **SCOPE, provider_name="yookassa", external_reference="payment-1",
    ).status == "pending"
