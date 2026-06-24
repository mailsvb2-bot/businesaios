from __future__ import annotations

from collections.abc import Mapping

from billing.recovery_contracts import ChargebackCase

from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.ledger_event import LedgerEntry, LedgerPosting, utc_now
from billing.lineage import derive_lineage_metadata
from billing.ledger_store import LedgerStoreContract
from billing.recovery_store import ChargebackStoreContract
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry
from runtime.monetization import ChargebackRecord, MonetizationService


CANON_BILLING_CHARGEBACK_ORCHESTRATOR = True




class InMemoryChargebackStore:
    def __init__(self) -> None:
        self._cases: dict[tuple[str, str], tuple[ChargebackCase, ...]] = {}
        self._by_idempotency: dict[tuple[str, str, str], ChargebackCase] = {}

    def save(self, case: ChargebackCase, *, idempotency_key: str | None = None) -> ChargebackCase:
        case.validate()
        key = (str(case.tenant_id), str(case.invoice_id))
        idem = None if idempotency_key is None else str(idempotency_key).strip()
        if idem:
            existing = self._by_idempotency.get((key[0], key[1], idem))
            if existing is not None:
                if existing != case:
                    raise ValueError('chargeback idempotency collision')
                return existing
        current = list(self._cases.get(key, ()))
        if any(item.case_id == case.case_id and item != case for item in current):
            raise ValueError('chargeback case collision')
        current.append(case)
        self._cases[key] = tuple(current)
        if idem:
            self._by_idempotency[(key[0], key[1], idem)] = case
        return case

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> ChargebackCase | None:
        return self._by_idempotency.get((str(tenant_id), str(invoice_id), str(idempotency_key).strip()))

    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple[ChargebackCase, ...]:
        return tuple(self._cases.get((str(tenant_id), str(invoice_id)), ()))


class ChargebackOrchestrator:
    def __init__(
        self,
        *,
        ledger_store: LedgerStoreContract,
        monetization_service: MonetizationService,
        case_store: ChargebackStoreContract | None = None,
        metrics: TenantMetricsRegistry | None = None,
        receivable_account: str = 'billing.accounts.ar',
        chargeback_account: str = 'billing.accounts.chargebacks',
    ) -> None:
        self._ledger_store = ledger_store
        self._monetization_service = monetization_service
        self._case_store = case_store or InMemoryChargebackStore()
        self._metrics = metrics
        self._receivable_account = str(receivable_account).strip() or 'billing.accounts.ar'
        self._chargeback_account = str(chargeback_account).strip() or 'billing.accounts.chargebacks'

    def open_case(self, *, invoice: CommercialInvoiceEnvelope, user_id: str, amount_minor: int, reason: str, metadata: Mapping[str, object] | None = None, idempotency_key: str | None = None) -> tuple[CommercialInvoiceEnvelope, ChargebackCase, ChargebackRecord, LedgerPosting]:
        invoice.validate()
        if invoice.status not in {invoice.status.ISSUED, invoice.status.PARTIALLY_PAID, invoice.status.PAID, invoice.status.UNCOLLECTIBLE}:
            raise ValueError('invoice is not eligible for chargeback')
        amount = int(amount_minor)
        normalized_idem = None if idempotency_key is None else str(idempotency_key).strip()
        existing = None if not normalized_idem else self._case_store.get_by_idempotency(tenant_id=invoice.tenant_id, invoice_id=invoice.invoice_id, idempotency_key=normalized_idem)
        if existing is None and amount > int(invoice.paid_minor):
            raise ValueError('chargeback amount cannot exceed invoice paid_minor')
        if existing is not None:
            posting = self._ledger_store.append(self._build_posting(case=existing))
            replay_record = ChargebackRecord(
                chargeback_id=str(existing.case_id),
                tenant_id=existing.tenant_id,
                user_id=existing.user_id,
                amount_minor=int(existing.amount_minor),
                currency=str(existing.currency).upper(),
                reason=str(existing.reason),
                status='opened',
            )
            seen_case_id = str(dict(invoice.metadata).get('last_chargeback_case_id') or dict(invoice.metadata).get('chargeback_case_id') or '')
            if seen_case_id == str(existing.case_id):
                return invoice, existing, replay_record, posting
            replay_paid_minor = max(0, int(invoice.paid_minor) - int(existing.amount_minor))
            replay_status = invoice.status.UNCOLLECTIBLE if int(existing.amount_minor) >= int(invoice.total_minor) else (invoice.status.ISSUED if replay_paid_minor == 0 else invoice.status.PARTIALLY_PAID)
            updated_invoice = CommercialInvoiceEnvelope(
                tenant_id=invoice.tenant_id,
                invoice_id=invoice.invoice_id,
                subscription_id=invoice.subscription_id,
                currency=invoice.currency,
                subtotal_minor=invoice.subtotal_minor,
                tax_minor=invoice.tax_minor,
                total_minor=invoice.total_minor,
                status=replay_status,
                issued_at=invoice.issued_at,
                due_at=invoice.due_at,
                paid_minor=replay_paid_minor,
                metadata=derive_lineage_metadata(invoice_id=invoice.invoice_id, invoice_metadata=invoice.metadata, event_type='chargeback', event_id=existing.case_id, idempotency_key=normalized_idem, extra={'last_chargeback_case_id': existing.case_id}),
            )
            updated_invoice.validate()
            return updated_invoice, existing, replay_record, posting
        case = ChargebackCase(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            user_id=str(user_id),
            amount_minor=amount,
            currency=invoice.currency,
            reason=str(reason),
            idempotency_key=normalized_idem,
            metadata=derive_lineage_metadata(
                invoice_id=invoice.invoice_id,
                invoice_metadata=invoice.metadata,
                event_type='chargeback',
                event_id=f"pending:{normalized_idem or 'manual'}",
                idempotency_key=normalized_idem,
                extra={'owner': 'billing.chargeback_orchestrator', **dict(metadata or {})},
            ),
        )
        stored_case = self._case_store.save(case, idempotency_key=normalized_idem)
        chargeback_record = self._monetization_service.record_chargeback(
            tenant_id=stored_case.tenant_id,
            user_id=stored_case.user_id,
            amount_minor=stored_case.amount_minor,
            currency=stored_case.currency,
            reason=stored_case.reason,
        )
        posting = self._ledger_store.append(self._build_posting(case=stored_case))
        updated_paid_minor = max(0, int(invoice.paid_minor) - amount)
        if amount >= int(invoice.total_minor):
            updated_status = invoice.status.UNCOLLECTIBLE
        elif updated_paid_minor == 0:
            updated_status = invoice.status.ISSUED
        else:
            updated_status = invoice.status.PARTIALLY_PAID
        updated_invoice = CommercialInvoiceEnvelope(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            subscription_id=invoice.subscription_id,
            currency=invoice.currency,
            subtotal_minor=invoice.subtotal_minor,
            tax_minor=invoice.tax_minor,
            total_minor=invoice.total_minor,
            status=updated_status,
            issued_at=invoice.issued_at,
            due_at=invoice.due_at,
            paid_minor=updated_paid_minor,
            metadata=derive_lineage_metadata(invoice_id=invoice.invoice_id, invoice_metadata=invoice.metadata, event_type='chargeback', event_id=stored_case.case_id, idempotency_key=normalized_idem, extra={'chargeback_case_id': stored_case.case_id, 'last_chargeback_case_id': stored_case.case_id}),
        )
        updated_invoice.validate()
        if self._metrics is not None:
            self._metrics.inc(tenant_id=stored_case.tenant_id, metric_name='billing_chargebacks_total', amount=1.0, labels={'currency': stored_case.currency.upper()})
        return updated_invoice, stored_case, chargeback_record, posting

    def _build_posting(self, *, case: ChargebackCase) -> LedgerPosting:
        case.validate()
        return LedgerPosting(
            posting_id=f'chargeback:{case.case_id}',
            tenant_id=case.tenant_id,
            reference_type='chargeback',
            reference_id=case.case_id,
            entries=(
                LedgerEntry(
                    tenant_id=case.tenant_id,
                    entry_id=f'{case.case_id}:debit',
                    account_code=self._chargeback_account,
                    side='debit',
                    amount_minor=case.amount_minor,
                    currency=case.currency,
                    reference_type='chargeback',
                    reference_id=case.case_id,
                    booked_at=case.opened_at,
                    metadata={'invoice_id': case.invoice_id},
                ),
                LedgerEntry(
                    tenant_id=case.tenant_id,
                    entry_id=f'{case.case_id}:credit',
                    account_code=self._receivable_account,
                    side='credit',
                    amount_minor=case.amount_minor,
                    currency=case.currency,
                    reference_type='chargeback',
                    reference_id=case.case_id,
                    booked_at=case.opened_at,
                    metadata={'invoice_id': case.invoice_id},
                ),
            ),
            metadata={'owner': 'billing.chargeback_orchestrator', 'invoice_id': case.invoice_id},
        )


__all__ = [
    'CANON_BILLING_CHARGEBACK_ORCHESTRATOR',
    'ChargebackCase',
    'ChargebackOrchestrator',
    'InMemoryChargebackStore',
]
