from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from collections.abc import Mapping
from uuid import uuid4

from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.ledger_event import LedgerEntry, LedgerPosting, utc_now
from billing.lineage import derive_lineage_metadata
from billing.ledger_store import LedgerStoreContract
from billing.recovery_store import RefundStoreContract
from billing.payment_provider_contract import PaymentProviderContract
from core.tenancy.normalization import require_tenant_id
from observability.tenant_metrics_registry import TenantMetricsRegistry
from runtime.monetization import MonetizationService, RefundRecord
from runtime.monetization import utc_now as monetization_utc_now


CANON_BILLING_REFUND_ORCHESTRATOR = True


@dataclass(frozen=True)
class RefundRequest:
    tenant_id: str
    invoice_id: str
    user_id: str
    amount_minor: int
    currency: str
    reason: str
    provider_name: str
    requested_at: datetime = field(default_factory=utc_now)
    idempotency_key: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if not str(self.user_id or '').strip():
            raise ValueError('user_id is required')
        if int(self.amount_minor) <= 0:
            raise ValueError('amount_minor must be > 0')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if not str(self.reason or '').strip():
            raise ValueError('reason is required')
        if not str(self.provider_name or '').strip():
            raise ValueError('provider_name is required')
        if self.requested_at.tzinfo is None:
            raise ValueError('requested_at must be timezone-aware')


@dataclass(frozen=True)
class RefundResult:
    tenant_id: str
    invoice_id: str
    refund_id: str
    amount_minor: int
    currency: str
    provider_name: str
    external_reference: str
    processed_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if not str(self.refund_id or '').strip():
            raise ValueError('refund_id is required')
        if int(self.amount_minor) <= 0:
            raise ValueError('amount_minor must be > 0')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if not str(self.provider_name or '').strip():
            raise ValueError('provider_name is required')
        if not str(self.external_reference or '').strip():
            raise ValueError('external_reference is required')
        if self.processed_at.tzinfo is None:
            raise ValueError('processed_at must be timezone-aware')


class InMemoryRefundStore:
    def __init__(self) -> None:
        self._by_idempotency: dict[tuple[str, str, str], RefundResult] = {}
        self._by_invoice: dict[tuple[str, str], tuple[RefundResult, ...]] = {}

    def save(self, result: RefundResult, *, idempotency_key: str | None = None) -> RefundResult:
        result.validate()
        invoice_key = (str(result.tenant_id), str(result.invoice_id))
        if idempotency_key is not None:
            key = (invoice_key[0], invoice_key[1], str(idempotency_key).strip())
            existing = self._by_idempotency.get(key)
            if existing is not None:
                if existing != result:
                    raise ValueError('idempotency_key collision for different refund result')
                return existing
        current = list(self._by_invoice.get(invoice_key, ()))
        if any(item.refund_id == result.refund_id and item != result for item in current):
            raise ValueError('refund_id collision for different refund result')
        current.append(result)
        self._by_invoice[invoice_key] = tuple(current)
        if idempotency_key is not None:
            self._by_idempotency[(invoice_key[0], invoice_key[1], str(idempotency_key).strip())] = result
        return result

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> RefundResult | None:
        return self._by_idempotency.get((str(tenant_id), str(invoice_id), str(idempotency_key).strip()))

    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple[RefundResult, ...]:
        return tuple(self._by_invoice.get((str(tenant_id), str(invoice_id)), ()))


class RefundOrchestrator:
    def __init__(
        self,
        *,
        provider: PaymentProviderContract,
        ledger_store: LedgerStoreContract,
        monetization_service: MonetizationService,
        invoice_lifecycle: InvoiceLifecycleService | None = None,
        refund_store: RefundStoreContract | None = None,
        metrics: TenantMetricsRegistry | None = None,
        clearing_account: str = 'billing.accounts.cash',
        contra_revenue_account: str = 'billing.accounts.refunds',
    ) -> None:
        self._provider = provider
        self._ledger_store = ledger_store
        self._monetization_service = monetization_service
        self._invoice_lifecycle = invoice_lifecycle or InvoiceLifecycleService()
        self._refund_store = refund_store or InMemoryRefundStore()
        self._metrics = metrics
        self._clearing_account = str(clearing_account).strip() or 'billing.accounts.cash'
        self._contra_revenue_account = str(contra_revenue_account).strip() or 'billing.accounts.refunds'

    def refund(
        self,
        *,
        invoice: CommercialInvoiceEnvelope,
        user_id: str,
        amount_minor: int,
        reason: str,
        idempotency_key: str,
        metadata: Mapping[str, object] | None = None,
    ) -> tuple[CommercialInvoiceEnvelope, RefundResult, RefundRecord, LedgerPosting]:
        invoice.validate()
        if invoice.status not in {invoice.status.ISSUED, invoice.status.PARTIALLY_PAID, invoice.status.PAID, invoice.status.UNCOLLECTIBLE}:
            raise ValueError('invoice is not eligible for refund')
        provider_affinity = self._extract_provider_affinity(invoice=invoice, metadata=metadata)
        requested = RefundRequest(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            user_id=str(user_id),
            amount_minor=int(amount_minor),
            currency=invoice.currency,
            reason=str(reason),
            provider_name=self._provider.provider_name(),
            idempotency_key=str(idempotency_key).strip(),
            metadata=dict(metadata or {}),
        )
        requested.validate()
        if provider_affinity is not None and str(requested.provider_name).strip().lower() != str(provider_affinity).strip().lower():
            raise ValueError('refund provider must match invoice provider affinity')
        if str(invoice.currency).strip().upper() != str(requested.currency).strip().upper():
            raise ValueError('refund currency must match invoice currency')
        existing = self._refund_store.get_by_idempotency(tenant_id=requested.tenant_id, invoice_id=requested.invoice_id, idempotency_key=requested.idempotency_key or '')
        if existing is None and requested.amount_minor > int(invoice.paid_minor):
            raise ValueError('refund amount cannot exceed paid_minor')
        if existing is not None:
            stored_posting = self._ledger_store.append(self._build_posting(result=existing))
            if str(dict(invoice.metadata).get('last_refund_id') or '') == str(existing.refund_id):
                replay_refund_record = RefundRecord(
                    refund_id=str(existing.refund_id),
                    tenant_id=requested.tenant_id,
                    user_id=requested.user_id,
                    amount_minor=int(existing.amount_minor),
                    currency=str(existing.currency).upper(),
                    reason=str(existing.metadata.get('reason') or requested.reason),
                    status='processed',
                    created_at=monetization_utc_now(),
                )
                return invoice, existing, replay_refund_record, stored_posting
            replayed_paid_minor = max(0, int(invoice.paid_minor) - int(existing.amount_minor))
            if replayed_paid_minor == 0:
                replayed_status = invoice.status.ISSUED
            elif replayed_paid_minor >= int(invoice.total_minor):
                replayed_status = invoice.status.PAID
            else:
                replayed_status = invoice.status.PARTIALLY_PAID
            updated_invoice = CommercialInvoiceEnvelope(
                tenant_id=invoice.tenant_id,
                invoice_id=invoice.invoice_id,
                subscription_id=invoice.subscription_id,
                currency=invoice.currency,
                subtotal_minor=invoice.subtotal_minor,
                tax_minor=invoice.tax_minor,
                total_minor=invoice.total_minor,
                status=replayed_status,
                issued_at=invoice.issued_at,
                due_at=invoice.due_at,
                paid_minor=replayed_paid_minor,
                metadata=derive_lineage_metadata(invoice_id=invoice.invoice_id, invoice_metadata=invoice.metadata, event_type='refund', event_id=existing.refund_id, idempotency_key=requested.idempotency_key, provider_name=existing.provider_name),
            )
            updated_invoice.validate()
            replay_refund_record = RefundRecord(
                refund_id=str(existing.refund_id),
                tenant_id=requested.tenant_id,
                user_id=requested.user_id,
                amount_minor=int(existing.amount_minor),
                currency=str(existing.currency).upper(),
                reason=str(existing.metadata.get('reason') or requested.reason),
                status='processed',
                created_at=monetization_utc_now(),
            )
            return updated_invoice, existing, replay_refund_record, stored_posting
        provider_payload = dict(self._provider.refund(
            invoice_id=requested.invoice_id,
            tenant_id=requested.tenant_id,
            amount_minor=requested.amount_minor,
            currency=requested.currency,
            reason=requested.reason,
            metadata={**dict(requested.metadata), 'idempotency_key': requested.idempotency_key},
        ) or {})
        external_reference = str(provider_payload.get('external_reference') or provider_payload.get('refund_id') or '').strip()
        if not external_reference:
            raise ValueError('provider refund result missing external_reference/refund_id')
        refund_id = str(provider_payload.get('refund_id') or uuid4())
        refund_result = RefundResult(
            tenant_id=requested.tenant_id,
            invoice_id=requested.invoice_id,
            refund_id=refund_id,
            amount_minor=requested.amount_minor,
            currency=requested.currency,
            provider_name=requested.provider_name,
            external_reference=external_reference,
            metadata=derive_lineage_metadata(
                invoice_id=requested.invoice_id,
                invoice_metadata=invoice.metadata,
                event_type='refund',
                event_id=refund_id,
                idempotency_key=requested.idempotency_key,
                provider_name=requested.provider_name,
                extra={
                    'owner': 'billing.refund_orchestrator',
                    'reason': requested.reason,
                    'idempotency_key': requested.idempotency_key,
                    **dict(requested.metadata),
                    **provider_payload,
                },
            ),
        )
        refund_result.validate()
        stored_result = self._refund_store.save(refund_result, idempotency_key=requested.idempotency_key)
        refund_record = self._monetization_service.record_refund(
            tenant_id=requested.tenant_id,
            user_id=requested.user_id,
            amount_minor=requested.amount_minor,
            currency=requested.currency,
            reason=requested.reason,
        )
        posting = self._ledger_store.append(self._build_posting(result=stored_result))
        new_paid_minor = max(0, int(invoice.paid_minor) - int(requested.amount_minor))
        if new_paid_minor == 0:
            new_status = invoice.status.ISSUED
        elif new_paid_minor >= int(invoice.total_minor):
            new_status = invoice.status.PAID
        else:
            new_status = invoice.status.PARTIALLY_PAID
        updated_invoice = CommercialInvoiceEnvelope(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            subscription_id=invoice.subscription_id,
            currency=invoice.currency,
            subtotal_minor=invoice.subtotal_minor,
            tax_minor=invoice.tax_minor,
            total_minor=invoice.total_minor,
            status=new_status,
            issued_at=invoice.issued_at,
            due_at=invoice.due_at,
            paid_minor=new_paid_minor,
            metadata=derive_lineage_metadata(invoice_id=invoice.invoice_id, invoice_metadata=invoice.metadata, event_type='refund', event_id=stored_result.refund_id, idempotency_key=requested.idempotency_key, provider_name=stored_result.provider_name, extra={'last_refund_id': stored_result.refund_id}),
        )
        updated_invoice.validate()
        if self._metrics is not None:
            self._metrics.inc(tenant_id=requested.tenant_id, metric_name='billing_refunds_total', amount=1.0, labels={'provider': requested.provider_name, 'currency': requested.currency.upper()})
        return updated_invoice, stored_result, refund_record, posting

    def _build_posting(self, *, result: RefundResult) -> LedgerPosting:
        result.validate()
        return LedgerPosting(
            posting_id=f'refund:{result.refund_id}',
            tenant_id=result.tenant_id,
            reference_type='refund',
            reference_id=result.refund_id,
            entries=(
                LedgerEntry(
                    tenant_id=result.tenant_id,
                    entry_id=f'{result.refund_id}:debit',
                    account_code=self._contra_revenue_account,
                    side='debit',
                    amount_minor=result.amount_minor,
                    currency=result.currency,
                    reference_type='refund',
                    reference_id=result.refund_id,
                    booked_at=result.processed_at,
                    metadata={'invoice_id': result.invoice_id, 'provider_name': result.provider_name},
                ),
                LedgerEntry(
                    tenant_id=result.tenant_id,
                    entry_id=f'{result.refund_id}:credit',
                    account_code=self._clearing_account,
                    side='credit',
                    amount_minor=result.amount_minor,
                    currency=result.currency,
                    reference_type='refund',
                    reference_id=result.refund_id,
                    booked_at=result.processed_at,
                    metadata={'invoice_id': result.invoice_id, 'provider_name': result.provider_name},
                ),
            ),
            metadata={'owner': 'billing.refund_orchestrator', 'invoice_id': result.invoice_id, 'external_reference': result.external_reference},
        )


    @staticmethod
    def _extract_provider_affinity(*, invoice: CommercialInvoiceEnvelope, metadata: Mapping[str, object] | None = None) -> str | None:
        merged = {**dict(invoice.metadata), **dict(metadata or {})}
        explicit = str(merged.get('preferred_provider') or merged.get('provider_name_hint') or merged.get('provider_name') or merged.get('routed_provider') or '').strip()
        if explicit:
            return explicit
        provider_customer_id = str(merged.get('provider_customer_id') or '').strip()
        if ':' in provider_customer_id:
            candidate = provider_customer_id.split(':', 1)[0].strip()
            return candidate or None
        return None


__all__ = [
    'CANON_BILLING_REFUND_ORCHESTRATOR',
    'InMemoryRefundStore',
    'RefundOrchestrator',
    'RefundRequest',
    'RefundResult',
]
