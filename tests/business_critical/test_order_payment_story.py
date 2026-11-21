"""Canonical invoice/checkout story never treats a manually paid invoice as PSP revenue."""
from adapters.api.fastapi.business_workspace_commercial_routes import _order_story


def _story(**overrides):
    values = dict(order_status="active", invoice_status="issued", amount_minor=10_000,
                  paid_minor=0, checkout_opened=False, provider_verified=False)
    return _order_story(**{**values, **overrides})


def test_payment_story_is_based_on_verified_provider_receipt():
    assert _story()["state"] == "awaiting_checkout"
    assert _story(checkout_opened=True)["state"] == "awaiting_payment"
    assert _story(invoice_status="partially_paid", paid_minor=5_000)["state"] == "partially_paid"
    assert _story(invoice_status="paid", paid_minor=10_000)["state"] == "needs_reconciliation"
    confirmed = _story(invoice_status="paid", paid_minor=10_000, checkout_opened=True, provider_verified=True)
    assert confirmed["state"] == "revenue_confirmed" and confirmed["counts_as_revenue"]
    assert all(row["done"] for row in confirmed["steps"])
    assert not _story(invoice_status="paid", paid_minor=10_000)["counts_as_revenue"]


def test_voided_and_reversed_orders_do_not_create_revenue():
    assert _story(invoice_status="void")["state"] == "closed_without_revenue"
    out = _story(order_status="cancelled", invoice_status="credited", paid_minor=10_000, provider_verified=True)
    assert out["state"] == "reversed" and out["counts_as_revenue"] is False


def test_provider_acceptance_never_confirms_partially_paid_invoice():
    row = _story(invoice_status="partially_paid", paid_minor=5_000, provider_verified=True)
    assert row["counts_as_revenue"] is False
