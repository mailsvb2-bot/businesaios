"""Commercial program purchase: locked catalogue price and authoritative payment gates."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
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


class Catalogs:
    def __init__(self, program_id):
        self.program_id, self.price, self.bound_business = program_id, 850, "business-a"

    def resolve(self, *, key):
        assert key.product_id == self.program_id and key.business_id == "business-a"
        return SimpleNamespace(id="program-catalog@v1", list_offers=lambda: [
            OfferSummary(
                offer_id="valid-offer", title="Existing program",
                base_price_rub=self.price,
                meta={"program_id": self.program_id, "business_id": self.bound_business},
            ),
        ])


def make_service():
    events, idem = MemoryEventStore(), InMemoryIdempotencyStore()
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    leads = LeadRegistry(event_store=events, idempotency_store=idem)
    leads.create(**scope, lead_id="lead-one", idempotency_key="lead-create",
                 customer_id="customer-one", conversation_id="conversation-one", channel="telegram")
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=idem)
    program = programs.publish(
        **scope, actor_id="owner", title="Existing paid program",
        lessons=[{"title": "Lesson", "content_kind": "text", "content_ref": "Material"}],
        idempotency_key="program-create",
    )
    offers = Catalogs(program["id"])
    orders = OrderStore(event_store=events)
    invoices = InvoiceRegistry(event_store=events, idempotency_store=idem)
    service = CommercialProgramPurchaseService(
        leads=leads, customers=Customers(), programs=programs,
        offers=offers, orders=orders, invoices=invoices,
    )
    return service, scope, program["id"], offers, orders, invoices, leads


def buy(service, scope, program_id):
    return service.prepare_purchase(
        **scope, lead_id="lead-one", customer_id="customer-one",
        program_id=program_id, offer_id="valid-offer", idempotency_key="buyer-request",
    )


def test_price_from_catalog_locked_and_idempotent_after_catalog_change():
    service, scope, pid, offers, orders, invoices, leads = make_service()
    first = buy(service, scope, pid)
    assert first.amount_minor == 85000
    assert first.currency == "RUB"
    assert first.invoice_status == "issued" and first.paid_minor == 0
    offers.price = 990
    assert buy(service, scope, pid) == first
    assert len(orders.list_for_business(**scope)) == 1
    assert len(invoices.list_for_business(**scope)) == 1
    with pytest.raises(ValueError, match="commercial_idempotency_conflict"):
        service.prepare_purchase(
            **scope, lead_id="lead-one", customer_id="another-customer",
            program_id=pid, offer_id="valid-offer", idempotency_key="buyer-request",
        )
    with pytest.raises(LookupError):
        orders.get_order_specialization(order_id=first.order_id,
            tenant_id="tenant-a", business_id="another-business")


def test_unbound_or_zero_price_refused_before_order():
    service, scope, pid, offers, orders, invoices, leads = make_service()
    offers.bound_business = "another-business"
    with pytest.raises(ValueError, match="commercial_offer_program_binding_invalid"):
        buy(service, scope, pid)
    offers.bound_business = "business-a"
    offers.price = 0
    with pytest.raises(ValueError, match="commercial_offer_price_invalid"):
        buy(service, scope, pid)
    assert orders.list_for_business(**scope) == ()
    assert invoices.list_for_business(**scope) == ()


def test_readiness_requires_full_invoice_and_verified_psp_and_no_reversal():
    service, scope, pid, offers, orders, invoices, leads = make_service()
    first = buy(service, scope, pid)
    def readiness(psp, reversed_payment):
        return service.execution_readiness(
            **scope, order_id=first.order_id,
            payment_evidence_reader=lambda **_: psp,
            reversal_reader=lambda **_: reversed_payment,
        )
    assert readiness(False, False).reason == "invoice_not_paid"
    invoices.record_payment(**scope, invoice_id=first.invoice_id,
                            idempotency_key="partial", amount_minor=40000)
    assert not readiness(True, False).eligible
    invoices.record_payment(**scope, invoice_id=first.invoice_id,
                            idempotency_key="settled", amount_minor=45000)
    assert readiness(False, False).reason == "psp_not_verified"
    assert readiness(True, True).reason == "payment_reversed_or_disputed"
    assert readiness(True, False).eligible
    with pytest.raises(RuntimeError, match="commercial_payment_authority_invalid"):
        readiness(1, False)
    with pytest.raises(RuntimeError, match="commercial_payment_authorities_required"):
        service.execution_readiness(
            **scope, order_id=first.order_id, payment_evidence_reader=None,
            reversal_reader=lambda **_: False,
        )
    leads.archive(**scope, lead_id="lead-one", idempotency_key="archived")
    assert readiness(True, False).reason == "party_or_program_not_active"


def test_failure_between_order_and_invoice_is_repairable_without_repricing():
    service, scope, pid, offers, orders, invoices, leads = make_service()
    original = invoices.create
    def unavailable(**kwargs):
        raise ConnectionError("invoice store temporarily unavailable")
    invoices.create = unavailable
    with pytest.raises(ConnectionError):
        buy(service, scope, pid)
    assert len(orders.list_for_business(**scope)) == 1
    invoices.create = original
    offers.price = 5000
    restored = buy(service, scope, pid)
    assert restored.amount_minor == 85000
    assert restored.invoice_status == "issued"
