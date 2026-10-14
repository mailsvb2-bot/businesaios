"""RUB/YooKassa and XTR/Stars share canonical checkout, invoice and entitlement."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.commerce.phase18_commercial_checkout import (
    build_dual_commercial_merchant_bundle,
    build_telegram_stars_commercial_bundle,
)
from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
from core.offers.offer_types import OfferSummary
from lead_outcomes.client_outcome_order_store import OrderStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from tests.integration.api.test_phase18_commercial_settlement_journey import Customers


class DualPriceOffers:
    def resolve(self, *, key):
        return SimpleNamespace(
            id="catalog-a",
            list_offers=lambda: [OfferSummary(
                offer_id="course", title="Course",
                base_price_rub=890, meta={
                    "program_id": key.product_id, "business_id": key.business_id,
                    "price_stars": 42,
                },
            )],
        )


def _environment():
    scope = dict(tenant_id="tenant-a", business_id="business-a")
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    leads = LeadRegistry(event_store=events, idempotency_store=claims)
    leads.create(
        **scope, lead_id="lead-a", customer_id="customer-a",
        conversation_id="conversation-a", channel="telegram", source="telegram",
        idempotency_key="lead-a", status="new",
    )
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=claims)
    program = programs.publish(
        **scope, actor_id="owner-a", title="Course", access_mode="paid",
        lessons=[{"title": "Lesson", "content_kind": "text", "content_ref": "Lesson text"}],
        idempotency_key="course",
    )
    purchases = CommercialProgramPurchaseService(
        leads=leads, customers=Customers(), programs=programs, offers=DualPriceOffers(),
        orders=OrderStore(event_store=events),
        invoices=InvoiceRegistry(event_store=events, idempotency_store=claims),
    )
    return scope, events, claims, purchases, program


def _stars(*, scope, events, claims, purchases, transactions):
    return build_telegram_stars_commercial_bundle(
        purchases=purchases, event_store=events, idempotency_store=claims,
        bot_id="bot-987", signing_secret=b"s" * 32,
        payer_resolver=lambda **kwargs: 183,
        sealed_create_invoice_link=lambda **kwargs: "https://t.me/$test-invoice",
        sealed_read_transactions=lambda: tuple(transactions),
    )


def _transaction(payload, *, charge="charge-1"):
    return {
        "id": charge, "amount": 42, "date": 1791970000,
        "source": {
            "type": "user", "transaction_type": "invoice_payment",
            "user": {"id": 183}, "invoice_payload": payload,
        },
    }


def test_stars_invoice_reconciliation_payment_replay_refund_and_restart():
    scope, events, claims, purchases, program = _environment()
    order = purchases.prepare_purchase(
        **scope, lead_id="lead-a", customer_id="customer-a",
        program_id=program["id"], offer_id="course",
        idempotency_key="buyer-stars", currency="XTR",
    )
    assert order.amount_minor == 42 and order.currency == "XTR"
    assert purchases.priced_offer(
        **scope, program_id=program["id"], offer_id="course", currency="RUB",
    ).amount_minor == 89000
    with pytest.raises(ValueError, match="idempotency_conflict"):
        purchases.prepare_purchase(
            **scope, lead_id="lead-a", customer_id="customer-a",
            program_id=program["id"], offer_id="course",
            idempotency_key="buyer-stars", currency="RUB",
        )
    transactions = []
    bound = _stars(
        scope=scope, events=events, claims=claims,
        purchases=purchases, transactions=transactions,
    )
    checkout = bound.checkout.open_checkout(**scope, order_id=order.order_id)
    assert checkout.currency == "XTR" and checkout.provider_name == "telegram_stars"
    assert checkout.checkout_url == "https://t.me/$test-invoice"
    assert bound.settlement.reconcile(**scope, order_id=order.order_id).provider_verified is False
    assert bound.paid_access.require_access(
        **scope, program_id=program["id"], customer_id="customer-a",
    ) is False

    transactions.append(_transaction(checkout.external_reference))
    confirmed = bound.settlement.reconcile(**scope, order_id=order.order_id)
    assert confirmed.provider_verified is True and confirmed.paid_minor == 42
    assert bound.settlement.reconcile(**scope, order_id=order.order_id) == confirmed
    assert bound.paid_access.require_access(
        **scope, program_id=program["id"], customer_id="customer-a",
    ) is True
    restarted = _stars(
        scope=scope, events=events, claims=claims, purchases=purchases,
        transactions=transactions,
    )
    assert restarted.checkout.open_checkout(**scope, order_id=order.order_id) == checkout
    assert restarted.settlement.reconcile(**scope, order_id=order.order_id) == confirmed

    transactions.append({
        "id": "charge-1", "amount": -42,
        "receiver": {"type": "user", "user": {"id": 183}},
    })
    assert restarted.paid_access.require_access(
        **scope, program_id=program["id"], customer_id="customer-a",
    ) is False
    assert restarted.settlement.reconcile(
        **scope, order_id=order.order_id,
    ).provider_verified is False
    assert purchases.invoices.get(
        **scope, invoice_id=order.invoice_id,
    ).paid_minor == 42


def test_two_providers_keep_one_invoice_owner_and_strict_provider_scope():
    scope, events, claims, purchases, program = _environment()
    transactions = []
    payment = {}

    def create_yookassa(**kwargs):
        payment.update({
            "id": "rub-payment-1", "status": "pending", "paid": False,
            "amount": {"value": "890.00", "currency": "RUB"},
            "confirmation": {"confirmation_url": "https://yookassa.ru/checkout/rub"},
            "metadata": kwargs["metadata"],
        })
        return dict(payment)

    combined = build_dual_commercial_merchant_bundle(
        purchases=purchases, event_store=events, idempotency_store=claims,
        merchant_id="rub-shop", sealed_create_payment=create_yookassa,
        sealed_fetch_payment=lambda _id: dict(payment),
        bot_id="stars-bot", signing_secret=b"s" * 32,
        payer_resolver=lambda **kwargs: 183,
        sealed_create_invoice_link=lambda **kwargs: "https://t.me/$stars",
        sealed_read_transactions=lambda: tuple(transactions),
    )
    orders = {}
    for currency in ("RUB", "XTR"):
        orders[currency] = purchases.prepare_purchase(
            **scope, lead_id="lead-a", customer_id="customer-a",
            program_id=program["id"], offer_id="course",
            idempotency_key=f"buyer-{currency}", currency=currency,
        )
        checkout = combined.checkout.open_checkout(
            **scope, order_id=orders[currency].order_id,
        )
        assert checkout.currency == currency
        assert checkout.provider_name == (
            "yookassa" if currency == "RUB" else "telegram_stars"
        )
    assert combined.settlement.reconcile(
        **scope, order_id=orders["XTR"].order_id,
    ).provider_verified is False
    xtr = combined.checkout._saved(
        **scope, order_id=orders["XTR"].order_id,
    )
    transactions.append(_transaction(xtr.external_reference))
    assert combined.settlement.reconcile(
        **scope, order_id=orders["XTR"].order_id,
    ).provider_verified is True
    assert combined.settlement.reconcile(
        **scope, order_id=orders["RUB"].order_id,
    ).provider_verified is False
    payment.update(status="succeeded", paid=True, captured_at="2026-10-14T13:00:00Z")
    assert combined.settlement.reconcile(
        **scope, order_id=orders["RUB"].order_id,
    ).provider_verified is True
    assert purchases.invoices.get(
        **scope, invoice_id=orders["RUB"].invoice_id,
    ).paid_minor == 89000
    assert purchases.invoices.get(
        **scope, invoice_id=orders["XTR"].invoice_id,
    ).paid_minor == 42
