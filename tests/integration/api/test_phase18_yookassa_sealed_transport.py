"""Checkout-to-authoritative-GET contract at the existing sealed transport boundary."""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from runtime._internal.effects_clients import yookassa_commercial_merchant as merchant


def test_authenticated_create_and_read_use_exact_merchant_api_and_idempotency(monkeypatch):
    calls = []
    monkeypatch.setattr(merchant, "resolve_credentials",
                        lambda: ("shop-1", "secret-test", "https://api.yookassa.ru"))
    monkeypatch.setattr(merchant, "env_str",
                        lambda key, default="": "https://shop.example/return")

    def fake_http(method, url, payload, *, headers, **kwargs):
        calls.append((method, url, payload, headers))
        assert headers["Authorization"].startswith("Basic ")
        if method == "POST":
            return {"id": "payment-1", "status": "pending"}
        return {"id": "payment-1", "status": "succeeded",
                "paid": True, "captured_at": "2026-10-13T12:00:00Z"}

    monkeypatch.setattr(merchant, "http_json", fake_http)
    metadata = {"tenant_id": "tenant-a", "business_id": "business-a",
                "order_id": "order-a", "invoice_id": "invoice-a",
                "program_id": "program-a"}
    merchant.create_merchant_payment(
        amount_minor=89000, currency="RUB", customer_id="customer-a",
        description="Published program", idempotency_key="checkout-order-a",
        metadata=metadata,
    )
    response = merchant.fetch_merchant_payment("payment-1")
    assert response["paid"] is True
    assert len(calls) == 2
    assert calls[0][0:2] == ("POST", "https://api.yookassa.ru/v3/payments")
    assert calls[0][2]["amount"] == {"value": "890.00", "currency": "RUB"}
    assert calls[0][2]["metadata"]["order_id"] == "order-a"
    assert calls[0][3]["Idempotence-Key"] == "checkout-order-a"
    assert calls[1][0:2] == ("GET", "https://api.yookassa.ru/v3/payments/payment-1")
    assert calls[1][2] is None


@pytest.mark.parametrize("url", [
    "http://shop.example/return", "https://example.com/return", "",
])
def test_bad_return_url_never_creates_payment(monkeypatch, url):
    monkeypatch.setattr(merchant, "env_str", lambda key, default="": url)
    monkeypatch.setattr(merchant, "http_json", Mock(side_effect=AssertionError("network forbidden")))
    with pytest.raises(RuntimeError, match="return_url"):
        merchant.create_merchant_payment(
            amount_minor=100, currency="RUB", customer_id="customer",
            description="Product", idempotency_key="once", metadata={},
        )


@pytest.mark.parametrize("id_", ["../refunds", "id?secret=x", "", "/payment-1"])
def test_payment_reference_cannot_escape_merchant_endpoint(id_):
    with pytest.raises(ValueError, match="payment_id_invalid"):
        merchant.fetch_merchant_payment(id_)


def test_mismatched_authenticated_response_cannot_claim_payment(monkeypatch):
    monkeypatch.setattr(merchant, "resolve_credentials",
                        lambda: ("shop-1", "secret-test", "https://api.yookassa.ru"))
    monkeypatch.setattr(merchant, "http_json", lambda *args, **kwargs: {
        "id": "different-payment", "status": "succeeded", "paid": True,
    })
    with pytest.raises(RuntimeError, match="payment_response_invalid"):
        merchant.fetch_merchant_payment("payment-1")


def test_untrusted_merchant_origin_is_rejected_before_network(monkeypatch):
    monkeypatch.setattr(merchant, "resolve_credentials",
                        lambda: ("shop-1", "secret-test", "https://untrusted.example"))
    monkeypatch.setattr(merchant, "http_json", Mock(side_effect=AssertionError("network forbidden")))
    with pytest.raises(RuntimeError, match="credentials_or_origin_invalid"):
        merchant.fetch_merchant_payment("payment-1")
