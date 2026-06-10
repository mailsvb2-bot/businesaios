from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Mapping

from billing.commercial_cycle_contract import InvoiceLifecycleStatus, utc_now
from core.tenancy.normalization import require_tenant_id

CANON_BILLING_INVOICE_LIFECYCLE = True


@dataclass(frozen=True)
class CommercialInvoiceEnvelope:
    tenant_id: str
    invoice_id: str
    subscription_id: str | None = None
    currency: str = 'USD'
    subtotal_minor: int = 0
    tax_minor: int = 0
    total_minor: int = 0
    status: InvoiceLifecycleStatus = InvoiceLifecycleStatus.DRAFT
    issued_at: datetime | None = None
    due_at: datetime | None = None
    paid_minor: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if int(self.subtotal_minor) < 0:
            raise ValueError('subtotal_minor must be >= 0')
        if int(self.tax_minor) < 0:
            raise ValueError('tax_minor must be >= 0')
        if int(self.total_minor) < 0:
            raise ValueError('total_minor must be >= 0')
        if int(self.subtotal_minor) != 0 or int(self.tax_minor) != 0:
            if int(self.subtotal_minor) + int(self.tax_minor) != int(self.total_minor):
                raise ValueError('subtotal_minor + tax_minor must equal total_minor')
        if int(self.paid_minor) < 0:
            raise ValueError('paid_minor must be >= 0')
        if int(self.paid_minor) > int(self.total_minor):
            raise ValueError('paid_minor cannot exceed total_minor')
        if self.issued_at is not None and self.issued_at.tzinfo is None:
            raise ValueError('issued_at must be timezone-aware')
        if self.due_at is not None and self.due_at.tzinfo is None:
            raise ValueError('due_at must be timezone-aware')
        if self.issued_at is not None and self.due_at is not None and self.due_at < self.issued_at:
            raise ValueError('due_at must be >= issued_at')
        if self.status in {InvoiceLifecycleStatus.ISSUED, InvoiceLifecycleStatus.PARTIALLY_PAID, InvoiceLifecycleStatus.PAID, InvoiceLifecycleStatus.UNCOLLECTIBLE} and self.issued_at is None:
            raise ValueError('issued-like invoice must have issued_at')
        if self.status is InvoiceLifecycleStatus.DRAFT and (self.issued_at is not None or int(self.paid_minor) > 0):
            raise ValueError('draft invoice cannot have issued_at or paid_minor')
        if self.status is InvoiceLifecycleStatus.VOID and int(self.paid_minor) > 0:
            raise ValueError('void invoice cannot have paid_minor')
        if self.status is InvoiceLifecycleStatus.PAID and int(self.paid_minor) != int(self.total_minor):
            raise ValueError('paid invoice must have paid_minor equal to total_minor')
        if self.status is InvoiceLifecycleStatus.PARTIALLY_PAID and not (0 < int(self.paid_minor) < int(self.total_minor)):
            raise ValueError('partially_paid invoice must have 0 < paid_minor < total_minor')

    @property
    def remaining_minor(self) -> int:
        return max(0, int(self.total_minor) - int(self.paid_minor))


class InvoiceLifecycleService:
    def issue(self, invoice: CommercialInvoiceEnvelope, *, issued_at: datetime | None = None, due_at: datetime | None = None) -> CommercialInvoiceEnvelope:
        invoice.validate()
        if invoice.status is not InvoiceLifecycleStatus.DRAFT:
            raise ValueError('invoice can only be issued from draft state')
        when = issued_at or utc_now()
        if when.tzinfo is None:
            raise ValueError('issued_at must be timezone-aware')
        if due_at is not None and due_at.tzinfo is None:
            raise ValueError('due_at must be timezone-aware')
        updated = replace(invoice, status=InvoiceLifecycleStatus.ISSUED, issued_at=when, due_at=due_at or invoice.due_at)
        updated.validate()
        return updated

    def record_payment(self, invoice: CommercialInvoiceEnvelope, *, amount_minor: int, paid_at: datetime | None = None) -> CommercialInvoiceEnvelope:
        invoice.validate()
        if invoice.status is InvoiceLifecycleStatus.DRAFT:
            raise ValueError('cannot record payment for draft invoice')
        if invoice.status in {InvoiceLifecycleStatus.VOID, InvoiceLifecycleStatus.CREDITED, InvoiceLifecycleStatus.UNCOLLECTIBLE}:
            raise ValueError('cannot record payment for closed invoice')
        effective_paid_at = paid_at or utc_now()
        if effective_paid_at.tzinfo is None:
            raise ValueError('paid_at must be timezone-aware')
        paid_delta = int(amount_minor)
        if paid_delta < 0:
            raise ValueError('amount_minor must be >= 0')
        if paid_delta == 0:
            return invoice
        new_paid = min(int(invoice.total_minor), int(invoice.paid_minor) + paid_delta)
        status = InvoiceLifecycleStatus.PAID if new_paid >= int(invoice.total_minor) else InvoiceLifecycleStatus.PARTIALLY_PAID
        issued_at = invoice.issued_at or effective_paid_at
        updated = replace(invoice, status=status, paid_minor=new_paid, issued_at=issued_at)
        updated.validate()
        return updated

    def void(self, invoice: CommercialInvoiceEnvelope) -> CommercialInvoiceEnvelope:
        invoice.validate()
        if invoice.status not in {InvoiceLifecycleStatus.DRAFT, InvoiceLifecycleStatus.ISSUED, InvoiceLifecycleStatus.UNCOLLECTIBLE}:
            raise ValueError('cannot void invoice from current state')
        if invoice.paid_minor > 0:
            raise ValueError('cannot void invoice with payments')
        updated = replace(invoice, status=InvoiceLifecycleStatus.VOID)
        updated.validate()
        return updated

    def credit(self, invoice: CommercialInvoiceEnvelope) -> CommercialInvoiceEnvelope:
        invoice.validate()
        if invoice.status not in {InvoiceLifecycleStatus.ISSUED, InvoiceLifecycleStatus.PARTIALLY_PAID, InvoiceLifecycleStatus.PAID, InvoiceLifecycleStatus.UNCOLLECTIBLE}:
            raise ValueError('cannot credit invoice from current state')
        if invoice.issued_at is None:
            raise ValueError('credited invoice must have been issued')
        updated = replace(invoice, status=InvoiceLifecycleStatus.CREDITED)
        updated.validate()
        return updated

    def mark_uncollectible(self, invoice: CommercialInvoiceEnvelope) -> CommercialInvoiceEnvelope:
        invoice.validate()
        if invoice.status not in {InvoiceLifecycleStatus.ISSUED, InvoiceLifecycleStatus.PARTIALLY_PAID}:
            raise ValueError('uncollectible is only allowed from issued/partially_paid')
        updated = replace(invoice, status=InvoiceLifecycleStatus.UNCOLLECTIBLE, issued_at=invoice.issued_at or utc_now())
        updated.validate()
        return updated


__all__ = ['CANON_BILLING_INVOICE_LIFECYCLE', 'CommercialInvoiceEnvelope', 'InvoiceLifecycleService']
