"""Phase 18 commercial sale proof over existing owners; no new ledger or CRM.

This is a read-only pre-fulfilment gate. A paid invoice is necessary, but it
does not prove customer delivery or permission to execute an outbound action.
The invoice must be loaded by the caller from the authoritative Billing owner,
not accepted as user-supplied HTTP JSON.
"""
from __future__ import annotations

from dataclasses import dataclass

from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope


@dataclass(frozen=True)
class SaleEvidence:
    tenant_id: str
    business_id: str
    lead_id: str
    program_id: str
    invoice_id: str
    payment_confirmed: bool
    product_published: bool
    lead_active: bool
    can_request_fulfilment: bool
    reason: str


def evaluate_sale_evidence(
    *, tenant_id: str, business_id: str, lead_id: str, program_id: str,
    invoice_id: str, leads, programs, invoice_reader, reversal_reader,
) -> SaleEvidence:
    """Compose canonical projections, fail closed on missing/stale/alien facts.

    A positive result is only *eligibility to request* the canonical Policy/
    ActionIntent execution path; this function never enqueues or delivers.
    """
    for key, value in (("tenant_id", tenant_id), ("business_id", business_id),
                       ("lead_id", lead_id), ("program_id", program_id),
                       ("invoice_id", invoice_id)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"sale_{key}_required")
    lead = leads.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)
    program = programs.get(tenant_id=tenant_id, business_id=business_id, program_id=program_id)
    invoice = invoice_reader(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)
    if not isinstance(invoice, CommercialInvoiceEnvelope):
        raise RuntimeError("sale_billing_authority_invalid")
    invoice.validate()
    if (invoice.tenant_id != tenant_id or invoice.business_id != business_id
            or invoice.invoice_id != invoice_id):
        raise RuntimeError("sale_billing_scope_mismatch")
    if (lead.tenant_id != tenant_id or lead.business_id != business_id or lead.lead_id != lead_id
            or program.get("tenant_id") != tenant_id
            or program.get("business_id") != business_id
            or program.get("id") != program_id):
        raise RuntimeError("sale_owner_scope_mismatch")
    # Missing a durable binding must never allow an unrelated paid invoice
    # to unlock this lead or program.
    meta = invoice.metadata
    if meta.get("lead_id") != lead_id or meta.get("program_id") != program_id:
        raise RuntimeError("sale_invoice_product_binding_missing")
    from contracts.lead import LeadLifecycleStatus
    lead_active = lead.lifecycle_status is LeadLifecycleStatus.ACTIVE
    published = program.get("status") == "active"
    paid = (invoice.status is InvoiceLifecycleStatus.PAID
            and type(invoice.total_minor) is int and invoice.total_minor > 0
            and type(invoice.paid_minor) is int
            and invoice.paid_minor == invoice.total_minor)
    # A PAID invoice projection alone is insufficient: refunds and chargebacks\n    # can be held by separate canonical finance owners. An absent authoritative\n    # reversal reader fails closed rather than silently granting fulfilment.\n    if not callable(reversal_reader):\n        raise RuntimeError("sale_reversal_authority_required")\n    reversal = reversal_reader(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)\n    if type(reversal) is not bool:\n        raise RuntimeError("sale_reversal_evidence_invalid")\n    allowed = lead_active and published and paid and not reversal
    reason = ("ready_for_governed_fulfilment" if allowed else
              "lead_inactive" if not lead_active else
              "product_not_published" if not published else
              "payment_not_confirmed" if not paid else "payment_reversed")
    return SaleEvidence(
        tenant_id=tenant_id, business_id=business_id, lead_id=lead_id,
        program_id=program_id, invoice_id=invoice_id,
        payment_confirmed=paid, product_published=published,
        lead_active=lead_active, can_request_fulfilment=allowed, reason=reason,
    )


__all__ = ["SaleEvidence", "evaluate_sale_evidence"]
