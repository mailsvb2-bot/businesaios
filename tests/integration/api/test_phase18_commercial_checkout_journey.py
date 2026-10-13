"""PSP sandbox checkout is durable provider evidence, never a paid invoice."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.commerce.phase18_commercial_checkout import CommercialCheckoutCoordinator
from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
from billing.payment_provider_contract import PaymentCheckoutSession
from contracts.customer import Customer, CustomerRecord
from core.offers.offer_types import OfferSummary
from lead_outcomes.client_outcome_order_store import OrderStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class Customers:
    def get_customer(self, *, tenant_id, business_id, customer_id):
        return CustomerRecord(customer=Customer(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
        ))


class Offers:
    def resolve(self, *, key):
        return SimpleNamespace(id="catalog-1", list_offers=lambda: [OfferSummary(
            offer_id="actual", title="Actual offer", base_price_rub=1200,
            meta={"program_id": key.product_id, "business_id": key.business_id},
        )])


class SandboxPSP:
    def __init__(self):
        self.calls = []
        self.status = "pending"
        self.checkout_url = "https://sandbox.example/pay/psp-1"

    def create_checkout(self, request):
        self.calls.append(request)
        return PaymentCheckoutSession(
            tenant_id=request.tenant_id, provider_name="sandbox",
            external_reference="psp-1", checkout_url=self.checkout_url,
            status="pending", amount_minor=request.amount_minor,
            currency=request.currency,
        )

    def get_payment_status(self, **kwargs):
        return self.status


def setup():
    events, idem = MemoryEventStore(), InMemoryIdempotencyStore()
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    leads = LeadRegistry(event_store=events, idempotency_store=idem)
    leads.create(**scope, lead_id="lead-a", idempotency_key="create-lead",
                 customer_id="customer-a", conversation_id="conversation-a", channel="telegram")
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=idem)
    program = programs.publish(
        access_mode="paid",
        **scope, actor_id="owner", title="Real training", idempotency_key="publish",
        lessons=[{"title": "Lesson", "content_kind": "text", "content_ref": "Material"}],
    )
    invoices = InvoiceRegistry(event_store=events, idempotency_store=idem)
    purchasing = CommercialProgramPurchaseService(
        leads=leads, customers=Customers(), programs=programs, offers=Offers(),
        orders=OrderStore(event_store=events), invoices=invoices,
    )
    order = purchasing.prepare_purchase(
        **scope, lead_id="lead-a", customer_id="customer-a",
        program_id=program["id"], offer_id="actual", idempotency_key="buy-a",
    )
    psp = SandboxPSP()
    checkout = CommercialCheckoutCoordinator(
        purchase_service=purchasing, payment_adapter=psp,
        event_store=events, idempotency_store=idem,
    )
    return scope, events, idem, purchasing, invoices, order, psp, checkout


def test_checkout_durable_replay_and_provider_status_never_assumed_payment():
    scope, events, idem, purchasing, invoices, order, psp, checkout = setup()
    first = checkout.open_checkout(**scope, order_id=order.order_id)
    assert first.amount_minor == order.amount_minor == 120000
    assert first.provider_name == "sandbox"
    assert len(psp.calls) == 1
    assert psp.calls[0].amount_minor == 120000
    assert psp.calls[0].metadata["invoice_id"] == order.invoice_id
    restarted = CommercialCheckoutCoordinator(
        purchase_service=purchasing, payment_adapter=psp,
        event_store=events, idempotency_store=idem,
    )
    assert restarted.open_checkout(**scope, order_id=order.order_id) == first
    assert len(psp.calls) == 1
    psp.status = "succeeded"
    observation = restarted.provider_observation(**scope, order_id=order.order_id)
    assert observation["provider_reported_status"] == "succeeded"
    assert observation["invoice_payment_confirmed"] is False
    assert invoices.get(**scope, invoice_id=order.invoice_id).status.value == "issued"
    with pytest.raises(LookupError):
        restarted.provider_observation(tenant_id="tenant-a", business_id="business-other",
                                       order_id=order.order_id)


def test_checkout_fails_closed_on_invalid_external_url_and_paid_invoice():
    scope, events, idem, purchasing, invoices, order, psp, checkout = setup()
    psp.checkout_url = "http://insecure.example/pay"
    with pytest.raises(RuntimeError, match="commercial_checkout_provider_session_invalid"):
        checkout.open_checkout(**scope, order_id=order.order_id)
    invoices.record_payment(
        **scope, invoice_id=order.invoice_id, amount_minor=order.amount_minor,
        idempotency_key="reconciled-by-finance",
    )
    with pytest.raises(ValueError, match="commercial_checkout_invoice_not_eligible"):
        checkout.open_checkout(**scope, order_id=order.order_id)
