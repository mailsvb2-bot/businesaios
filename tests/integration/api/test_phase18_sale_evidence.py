"""Phase18 canonical-sale evidence: no paid-product unlock from unrelated receipts."""
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from application.commerce.phase18_sale_evidence import evaluate_sale_evidence
from application.commerce.phase18_program_publication_registry import ProgramPublicationRegistry
from application.lead.registry import LeadRegistry
from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_sale_requires_owned_paid_invoice_published_program_and_live_lead():
    events = MemoryEventStore()
    idem = InMemoryIdempotencyStore()
    leads = LeadRegistry(event_store=events, idempotency_store=idem)
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=idem)
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    lead = leads.create(**scope, lead_id="lead-1", idempotency_key="lead-create")
    program = programs.publish(
        **scope, actor_id="owner", title="Training",
        lessons=[{"title": "Intro", "content_kind": "text", "content_ref": "Lesson"}],
        idempotency_key="program-create",
    )
    invoice = CommercialInvoiceEnvelope(
        **scope, invoice_id="invoice-1", currency="RUB", total_minor=10000,
        metadata={"lead_id": lead.lead_id, "program_id": program["id"]},
    )
    billing = InvoiceLifecycleService()
    invoice = billing.issue(invoice, issued_at=datetime(2026, 10, 12, tzinfo=timezone.utc))
    invoices = {"invoice-1": invoice}
    def read_invoice(*, tenant_id, business_id, invoice_id):
        assert (tenant_id, business_id) == ("tenant-a", "business-a")
        return invoices[invoice_id]
    args = dict(**scope, lead_id="lead-1", program_id=program["id"],
                invoice_id="invoice-1", leads=leads, programs=programs,
                invoice_reader=read_invoice, reversal_reader=lambda **_: False)
    unpaid = evaluate_sale_evidence(**args)
    assert unpaid.can_request_fulfilment is False
    assert unpaid.reason == "payment_not_confirmed"
    invoices["invoice-1"] = billing.record_payment(invoice, amount_minor=4000)
    partial = evaluate_sale_evidence(**args)
    assert partial.can_request_fulfilment is False
    invoices["invoice-1"] = billing.record_payment(invoices["invoice-1"], amount_minor=6000)
    paid = evaluate_sale_evidence(**args)
    assert paid.payment_confirmed and paid.can_request_fulfilment
    assert paid.reason == "ready_for_governed_fulfilment"
    assert len(events) == 2  # read-only gate makes no business facts

    original = invoices["invoice-1"]
    for changed in (
        replace(original, business_id="another-business"),
        replace(original, tenant_id="another-tenant"),
        replace(original, metadata={"lead_id": "different-lead", "program_id": program["id"]}),
        replace(original, metadata={"lead_id": "lead-1", "program_id": "different-program"}),
    ):
        invoices["invoice-1"] = changed
        with pytest.raises(RuntimeError, match="sale_billing_scope_mismatch|sale_invoice_product_binding_missing"):
            evaluate_sale_evidence(**args)
    assert evaluate_sale_evidence(**{**args, "reversal_reader": lambda **_: True}).reason == "payment_reversed"
    with pytest.raises(RuntimeError, match="sale_reversal_authority_required"):
        evaluate_sale_evidence(**{**args, "reversal_reader": None})
    with pytest.raises(RuntimeError, match="sale_reversal_evidence_invalid"):
        evaluate_sale_evidence(**{**args, "reversal_reader": lambda **_: None})
    invoices["invoice-1"] = replace(original, status=InvoiceLifecycleStatus.CREDITED)
    assert not evaluate_sale_evidence(**args).can_request_fulfilment
    invoices["invoice-1"] = original
    leads.archive(**scope, lead_id="lead-1", idempotency_key="archive")
    assert evaluate_sale_evidence(**args).reason == "lead_inactive"
    with pytest.raises((LookupError, KeyError)):
        evaluate_sale_evidence(**{**args, "business_id": "different-business"})


def test_sale_reads_durable_canonical_invoice_after_registry_restart():
    from billing.invoice_registry import InvoiceRegistry

    events, idem = MemoryEventStore(), InMemoryIdempotencyStore()
    scope = {"tenant_id": "tenant-a", "business_id": "business-a"}
    leads = LeadRegistry(event_store=events, idempotency_store=idem)
    programs = ProgramPublicationRegistry(event_store=events, idempotency_store=idem)
    first_billing = InvoiceRegistry(event_store=events, idempotency_store=idem)
    leads.create(**scope, lead_id="lead-one", idempotency_key="lead-one")
    program = programs.publish(
        **scope, actor_id="owner", title="Paid lessons", idempotency_key="course",
        lessons=[{"title": "Lesson", "content_kind": "text", "content_ref": "Text"}],
    )
    invoice = CommercialInvoiceEnvelope(
        **scope, invoice_id="invoice-one", currency="RUB",
        total_minor=15000, metadata={"lead_id": "lead-one", "program_id": program["id"]},
    )
    first_billing.create(business_id=scope["business_id"], invoice=invoice, idempotency_key="create")
    first_billing.issue(**scope, invoice_id="invoice-one", idempotency_key="issue",
                        issued_at=datetime(2026, 10, 12, tzinfo=timezone.utc))
    first_billing.record_payment(**scope, invoice_id="invoice-one",
                                 idempotency_key="payment", amount_minor=15000)
    restarted = InvoiceRegistry(event_store=events, idempotency_store=idem)
    args = dict(**scope, lead_id="lead-one", program_id=program["id"],
                invoice_id="invoice-one", leads=leads, programs=programs,
                invoice_reader=restarted.get, reversal_reader=lambda **_: False)
    assert evaluate_sale_evidence(**args).can_request_fulfilment is True
    # A reverse-payment observation from the canonical finance owner overrides
    # the durable paid invoice projection until it has been reconciled.
    assert evaluate_sale_evidence(**{**args, "reversal_reader": lambda **_: True}).can_request_fulfilment is False
    restarted.credit(**scope, invoice_id="invoice-one", idempotency_key="credit")
    assert evaluate_sale_evidence(**args).can_request_fulfilment is False
    assert evaluate_sale_evidence(**args).reason == "payment_not_confirmed"
