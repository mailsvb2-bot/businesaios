"""Full canonical lead -> paid program -> merchant settlement -> entitlement proof."""
from __future__ import annotations

from application.commerce.phase18_commercial_provider_binding import build_yookassa_commercial_bundle
from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
from lead_outcomes.client_outcome_order_store import OrderStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from tests.integration.api.test_phase18_commercial_settlement_journey import Customers, Offers


def test_merchant_read_drives_one_canonical_invoice_and_revokes_access_on_refund():
    scope = dict(tenant_id="tenant-a", business_id="business-a")
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    leads = LeadRegistry(event_store=events, idempotency_store=claims)
    leads.create(**scope, lead_id="lead-a", customer_id="customer-a",
                 conversation_id="conversation-a", channel="telegram",
                 idempotency_key="new-lead", status="new", source="telegram")
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=claims)
    program = programs.publish(
        **scope, access_mode="paid", actor_id="owner-a", title="Published course",
        lessons=[{"title": "Lesson 1", "content_kind": "text", "content_ref": "First lesson"}],
        idempotency_key="program-1",
    )
    purchases = CommercialProgramPurchaseService(
        leads=leads, customers=Customers(), programs=programs, offers=Offers(),
        orders=OrderStore(event_store=events),
        invoices=InvoiceRegistry(event_store=events, idempotency_store=claims),
    )
    order = purchases.prepare_purchase(
        **scope, lead_id="lead-a", customer_id="customer-a",
        program_id=program["id"], offer_id="course", idempotency_key="buyer-one",
    )
    snapshot = {}
    def create(*, amount_minor, currency, customer_id, description, idempotency_key, metadata):
        assert amount_minor == order.amount_minor and currency == "RUB"
        assert metadata["tenant_id"] == "tenant-a"
        snapshot.update({
            "id": "merchant-payment-1", "status": "pending", "paid": False,
            "amount": {"value": "890.00", "currency": "RUB"},
            "confirmation": {"confirmation_url": "https://yookassa.ru/checkout/merchant-1"},
            "metadata": metadata,
        })
        return dict(snapshot)

    def read(payment_id):
        assert payment_id == "merchant-payment-1"
        return dict(snapshot)

    bound = build_yookassa_commercial_bundle(
        purchases=purchases, event_store=events, idempotency_store=claims,
        merchant_id="merchant-a", sealed_create_payment=create, sealed_fetch_payment=read,
    )
    checkout = bound.checkout.open_checkout(**scope, order_id=order.order_id)
    assert checkout.external_reference == "merchant-payment-1"
    assert bound.settlement.reconcile(**scope, order_id=order.order_id).provider_verified is False
    assert bound.paid_access.require_access(
        **scope, customer_id="customer-a", program_id=program["id"],
    ) is False

    snapshot.update(status="succeeded", paid=True, captured_at="2026-10-13T12:00:00Z")
    paid = bound.settlement.reconcile(**scope, order_id=order.order_id)
    assert paid.provider_verified is True
    assert paid.paid_minor == order.amount_minor
    assert bound.settlement.reconcile(**scope, order_id=order.order_id) == paid
    assert bound.paid_access.require_access(
        **scope, customer_id="customer-a", program_id=program["id"],
    ) is True
    snapshot["refunded_amount"] = {"value": "100.00", "currency": "RUB"}
    assert bound.paid_access.require_access(
        **scope, customer_id="customer-a", program_id=program["id"],
    ) is False

    restored = InvoiceRegistry(event_store=events, idempotency_store=claims)
    assert restored.get(**scope, invoice_id=order.invoice_id).paid_minor == 89000
    assert restored.has_verified_psp_payment_evidence(
        **scope, invoice_id=order.invoice_id,
        evidence_id="yookassa:payment:merchant-payment-1",
    ) is True
