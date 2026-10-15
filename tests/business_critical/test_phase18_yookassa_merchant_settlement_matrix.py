"""Adversarial merchant-read contract for Phase-18 YooKassa settlement.

The callback body is never authoritative: only the bound merchant GET result
may produce evidence for the canonical InvoiceRegistry reconciler.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from billing.phase18_commercial_settlement import YooKassaCommercialAuthority


_SCOPE = {"tenant_id": "tenant-a", "business_id": "business-a",
          "provider_name": "yookassa", "external_reference": "payment-1"}


def _authority(*, changes=None, checkout_changes=None):
    checkout = {
        "provider_name": "yookassa", "external_reference": "payment-1",
        "tenant_id": "tenant-a", "business_id": "business-a",
        "order_id": "order-1", "invoice_id": "invoice-1",
        "amount_minor": 89000, "currency": "RUB",
    }
    checkout.update(checkout_changes or {})
    snapshot = {
        "id": "payment-1",
        "metadata": {"tenant_id": "tenant-a", "business_id": "business-a",
                     "order_id": "order-1", "invoice_id": "invoice-1"},
        "amount": {"value": "890.00", "currency": "RUB"},
        "status": "succeeded", "paid": True,
        "captured_at": "2026-10-14T12:00:00Z",
    }
    for key, value in (changes or {}).items():
        if key.startswith("metadata."):
            snapshot["metadata"][key.split(".", 1)[1]] = value
        elif key.startswith("amount."):
            snapshot["amount"][key.split(".", 1)[1]] = value
        else:
            snapshot[key] = value
    requests = []

    def merchant_get(payment_id):
        requests.append(payment_id)
        return snapshot

    authority = YooKassaCommercialAuthority(
        merchant_id="shop-1", create_payment=lambda **kwargs: None,
        fetch_payment=merchant_get,
        checkout_reader=lambda **kwargs: SimpleNamespace(**checkout),
    )
    return authority, requests


def _proof(authority):
    return authority.fetch_settlement_evidence(**_SCOPE)


def test_exact_merchant_snapshot_is_verifiable_without_webhook_claim():
    authority, reads = _authority()
    proof = _proof(authority)
    assert proof.status == "succeeded"
    assert proof.amount_minor == 89000
    assert proof.merchant_id == "shop-1"
    assert proof.external_reference == "payment-1"
    assert proof.order_id == "order-1"
    assert proof.invoice_id == "invoice-1"
    assert proof.tenant_id == "tenant-a"
    assert proof.business_id == "business-a"
    assert proof.evidence_id == "yookassa:payment:payment-1"
    assert reads == ["payment-1"]


@pytest.mark.parametrize("changes", [
    {"id": "other-payment"},
    {"metadata.tenant_id": "tenant-b"},
    {"metadata.business_id": "business-b"},
    {"metadata.order_id": "order-2"},
    {"metadata.invoice_id": "invoice-2"},
    {"amount.value": "889.99"},
    {"amount.value": "890.01"},
    {"amount.value": "NaN"},
    {"amount.value": "Infinity"},
    {"amount.value": "890.001"},
    {"amount.currency": "USD"},
    {"status": "unrecognized"},
])
def test_forged_or_ambiguous_merchant_fact_never_verifies(changes):
    authority, reads = _authority(changes=changes)
    with pytest.raises(RuntimeError):
        _proof(authority)
    assert reads == ["payment-1"]


@pytest.mark.parametrize("changes", [
    {"status": "pending", "paid": False, "captured_at": None},
    {"status": "waiting_for_capture", "paid": False, "captured_at": None},
    {"status": "canceled", "paid": False, "captured_at": None},
    {"paid": False},
    {"captured_at": None},
])
def test_nonterminal_or_uncaptured_money_never_becomes_verified(changes):
    authority, _ = _authority(changes=changes)
    assert _proof(authority).status == "pending"


@pytest.mark.parametrize("checkout_changes", [
    {"external_reference": "other-payment"},
    {"provider_name": "other-provider"},
])
def test_nonmatching_checkout_binding_blocks_merchant_read(checkout_changes):
    authority, reads = _authority(checkout_changes=checkout_changes)
    with pytest.raises(RuntimeError, match="checkout_not_bound"):
        _proof(authority)
    assert reads == []


@pytest.mark.parametrize("changes", [
    {"refunded_amount": {"value": "1.00", "currency": "RUB"}},
    {"refunded_amount": {"value": "890.00", "currency": "RUB"}},
])
def test_refunded_payment_is_not_fresh_settlement(changes):
    authority, _ = _authority(changes=changes)
    assert _proof(authority).status == "refunded"


@pytest.mark.parametrize("changes", [
    {"refunded_amount": {"value": "891.00", "currency": "RUB"}},
    {"refunded_amount": {"value": "NaN", "currency": "RUB"}},
    {"refunded_amount": {"value": "1.00", "currency": "USD"}},
])
def test_malformed_or_excess_refund_fact_fails_closed(changes):
    authority, _ = _authority(changes=changes)
    with pytest.raises(RuntimeError):
        _proof(authority)
