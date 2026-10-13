"""Real canonical sales snapshot: no PII, no stale AI actions, no false payments."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.commerce.phase18_commercial_context import CommercialJourneyContextReader
from application.commerce.phase18_commercial_order import CommercialProgramPurchaseService
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.invoice_registry import InvoiceRegistry
from contracts.messaging_event_identity import MessageDirection, MessageIdentity
from core.offers.offer_types import OfferSummary
from crm.customer_registry import CustomerRegistry
from lead_outcomes.client_outcome_order_store import OrderStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.messaging.conversation_registry import ConversationRegistry
from runtime.messaging.message_registry import MessageRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from security.secret_vault import InMemorySecretVault


class Offers:
    def resolve(self, *, key):
        return SimpleNamespace(id="catalog@v1", list_offers=lambda: [OfferSummary(
            offer_id="verified", title="Published", base_price_rub=400,
            meta={"program_id": key.product_id, "business_id": key.business_id},
        )])


def _build():
    events, claims = MemoryEventStore(), InMemoryIdempotencyStore()
    scope = dict(tenant_id="tenant-a", business_id="business-a")
    customers = CustomerRegistry(event_store=events, idempotency_store=claims,
                                 pii_vault=InMemorySecretVault())
    customer = customers.ensure_customer_identity(
        **scope, channel="telegram", external_subject="123",
    ).customer
    conversations = ConversationRegistry(event_store=events, idempotency_store=claims,
                                         customer_registry=customers)
    conversation = conversations.ensure_ingress(
        **scope, customer_id=customer.customer_id, channel="telegram",
        route_ref="chat:123", contact_id="message:1",
    )
    messages = MessageRegistry(event_store=events, idempotency_store=claims)
    first = messages.record(
        identity=MessageIdentity(message_id="message:1", **scope, channel="telegram",
                                 direction=MessageDirection.INBOUND),
        customer_id=customer.customer_id, conversation_id=conversation.conversation_id,
    )
    leads = LeadRegistry(event_store=events, idempotency_store=claims)
    lead = leads.create(
        **scope, lead_id="canonical-lead", idempotency_key="create-lead",
        customer_id=customer.customer_id, conversation_id=conversation.conversation_id,
        channel="telegram", source="telegram", status="new",
    )
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=claims,
                                          customer_registry=customers)
    published = programs.publish(
        access_mode="paid",
        **scope, actor_id="owner", title="Course", idempotency_key="create-program",
        lessons=[{"title": "Start", "content_kind": "text", "content_ref": "Material"}],
    )
    orders = OrderStore(event_store=events)
    invoices = InvoiceRegistry(event_store=events, idempotency_store=claims)
    context = CommercialJourneyContextReader(
        leads=leads, customers=customers, conversations=conversations,
        messages=messages, programs=programs, orders=orders, invoices=invoices,
    )
    purchase = CommercialProgramPurchaseService(
        leads=leads, customers=customers, programs=programs,
        offers=Offers(), orders=orders, invoices=invoices,
    )
    return locals()


def test_snapshot_detects_message_price_invoice_and_stage_changes():
    ctx = _build()
    scope = ctx["scope"]
    service = ctx["context"]
    lead_id = ctx["lead"].lead_id
    before = service.read(**scope, lead_id=lead_id)
    assert before.inbound_message_count == 1
    assert before.latest_message_id == ctx["first"].message_id
    assert before.sales_stage == "new"
    assert before.active_program_ids == (ctx["published"]["id"],)
    assert before.orders == ()
    assert before.can_prepare_offer is True
    assert service.require_current(**scope, lead_id=lead_id,
                                   expected_fingerprint=before.context_fingerprint) == before

    ctx["leads"].update(**scope, lead_id=lead_id, status="qualified",
                        idempotency_key="qualify")
    with pytest.raises(RuntimeError, match="commercial_context_stale_decision"):
        service.require_current(**scope, lead_id=lead_id,
                                expected_fingerprint=before.context_fingerprint)
    new_stage = service.read(**scope, lead_id=lead_id)
    assert new_stage.sales_stage == "qualified"

    order = ctx["purchase"].prepare_purchase(
        **scope, lead_id=lead_id, customer_id=ctx["customer"].customer_id,
        program_id=ctx["published"]["id"], offer_id="verified",
        idempotency_key="buy-program",
    )
    with_order = service.read(**scope, lead_id=lead_id)
    assert len(with_order.orders) == 1
    snapshot_order = with_order.orders[0]
    assert snapshot_order.order_id == order.order_id
    assert snapshot_order.billing_status == "issued"
    assert snapshot_order.external_payment_verified is False
    assert snapshot_order.delivery_verified is False
    assert snapshot_order.paid_minor == 0
    ctx["invoices"].record_payment(**scope, invoice_id=order.invoice_id,
                                   amount_minor=order.amount_minor, idempotency_key="settled")
    after_invoice = service.read(**scope, lead_id=lead_id)
    assert after_invoice.context_fingerprint != with_order.context_fingerprint
    assert after_invoice.orders[0].billing_status == "paid"
    assert after_invoice.orders[0].external_payment_verified is False


def test_snapshot_rejects_foreign_lead_and_closed_conversation():
    ctx = _build()
    scope, reader = ctx["scope"], ctx["context"]
    lead = ctx["lead"]
    with pytest.raises(LookupError):
        reader.read(tenant_id="tenant-a", business_id="business-b", lead_id=lead.lead_id)
    expected = reader.read(**scope, lead_id=lead.lead_id)
    ctx["leads"].archive(**scope, lead_id=lead.lead_id, idempotency_key="archive")
    with pytest.raises(RuntimeError, match="commercial_context_customer_or_conversation_closed"):
        reader.require_current(**scope, lead_id=lead.lead_id,
                               expected_fingerprint=reader.read(**scope, lead_id=lead.lead_id).context_fingerprint)
    with pytest.raises(RuntimeError, match="commercial_context_stale_decision"):
        reader.require_current(**scope, lead_id=lead.lead_id,
                               expected_fingerprint=expected.context_fingerprint)


def test_canonical_funnel_advisory_uses_live_customer_and_order_facts_not_fake_payment():
    ctx = _build()
    reader, scope, lead = ctx["context"], ctx["scope"], ctx["lead"]
    first = reader.read_funnel_advisory(**scope, lead_id=lead.lead_id)
    assert first["derived_stage"] == "engaged"
    assert first["advisory_only"] is True
    assert first["externally_verified_payment"] is False
    ctx["leads"].update(**scope, lead_id=lead.lead_id, status="qualified",
                        idempotency_key="advisory-stage-qualified")
    qualified = reader.read_funnel_advisory(**scope, lead_id=lead.lead_id)
    assert qualified["derived_stage"] == "qualified"
    assert qualified["context_fingerprint"] != first["context_fingerprint"]
    order = ctx["purchase"].prepare_purchase(
        **scope, lead_id=lead.lead_id, customer_id=ctx["customer"].customer_id,
        program_id=ctx["published"]["id"], offer_id="verified",
        idempotency_key="advisory-create-order",
    )
    ctx["invoices"].record_payment(**scope, invoice_id=order.invoice_id,
                                   amount_minor=order.amount_minor,
                                   idempotency_key="advisory-unverified-invoice")
    after = reader.read_funnel_advisory(**scope, lead_id=lead.lead_id)
    assert after["has_order"] is True
    assert after["externally_verified_payment"] is False
    assert after["derived_stage"] != "won"
    with pytest.raises(LookupError):
        reader.read_funnel_advisory(
            tenant_id=scope["tenant_id"], business_id="foreign-business",
            lead_id=lead.lead_id,
        )
