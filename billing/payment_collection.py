from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from billing.commercial_cycle_contract import (
    CommercialCollectionAttempt,
    CommercialCollectionResult,
    require_commercial_int,
    utc_now,
)
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.payment_provider_contract import PaymentProviderContract
from observability.tenant_metrics_registry import TenantMetricsRegistry

CANON_BILLING_PAYMENT_COLLECTION = True


@dataclass
class InMemoryCollectionResultStore:
    results_by_invoice: dict[tuple[str, str], tuple[CommercialCollectionResult, ...]] = field(default_factory=dict)
    idempotency_index: dict[tuple[str, str, str], CommercialCollectionResult] = field(default_factory=dict)

    def append(
        self, result: CommercialCollectionResult, *, idempotency_key: str | None = None
    ) -> CommercialCollectionResult:
        result.validate()
        tenant_invoice_key = (str(result.tenant_id), str(result.invoice_id))
        if idempotency_key is not None:
            idem_key = (tenant_invoice_key[0], tenant_invoice_key[1], str(idempotency_key))
            existing = self.idempotency_index.get(idem_key)
            if existing is not None:
                if existing != result:
                    raise ValueError("idempotency_key collision for different collection result")
                return existing
        current = list(self.results_by_invoice.get(tenant_invoice_key, ()))
        current.append(result)
        self.results_by_invoice[tenant_invoice_key] = tuple(current)
        if idempotency_key is not None:
            self.idempotency_index[(tenant_invoice_key[0], tenant_invoice_key[1], str(idempotency_key))] = result
        return result

    def list_for_invoice(
        self, invoice_id: str, *, tenant_id: str | None = None
    ) -> tuple[CommercialCollectionResult, ...]:
        normalized_invoice_id = str(invoice_id)
        if tenant_id is not None:
            return tuple(self.results_by_invoice.get((str(tenant_id), normalized_invoice_id), ()))
        return tuple(
            item
            for (_, scoped_invoice_id), items in self.results_by_invoice.items()
            if scoped_invoice_id == normalized_invoice_id
            for item in items
        )

    def get_by_idempotency(
        self, *, tenant_id: str, invoice_id: str, idempotency_key: str
    ) -> CommercialCollectionResult | None:
        return self.idempotency_index.get((str(tenant_id), str(invoice_id), str(idempotency_key)))


class PaymentCollectionOrchestrator:
    def __init__(
        self,
        *,
        provider: PaymentProviderContract,
        invoice_lifecycle: InvoiceLifecycleService | None = None,
        result_store: InMemoryCollectionResultStore | None = None,
        metrics: TenantMetricsRegistry | None = None,
    ) -> None:
        self._provider = provider
        self._invoice_lifecycle = invoice_lifecycle or InvoiceLifecycleService()
        self._result_store = result_store or InMemoryCollectionResultStore()
        self._metrics = metrics

    def collect(
        self,
        *,
        invoice: CommercialInvoiceEnvelope,
        idempotency_key: str,
        attempt_no: int = 1,
        metadata: Mapping[str, object] | None = None,
    ) -> tuple[CommercialInvoiceEnvelope, CommercialCollectionResult]:
        invoice.validate()
        normalized_key = str(idempotency_key or "").strip()
        if not normalized_key:
            raise ValueError("idempotency_key is required")
        existing = self._result_store.get_by_idempotency(
            tenant_id=invoice.tenant_id, invoice_id=invoice.invoice_id, idempotency_key=normalized_key
        )
        if existing is not None:
            if invoice.status.value in {"draft", "void", "credited"}:
                raise ValueError("cannot replay collection into current invoice state")
            existing_metadata = dict(existing.metadata)
            if str(existing.provider_name).strip() != str(self._provider.provider_name()).strip():
                raise ValueError("replayed collection provider mismatch")
            if (
                str(existing_metadata.get("currency", invoice.currency)).strip().upper()
                != str(invoice.currency).strip().upper()
            ):
                raise ValueError("replayed collection currency mismatch")
            replayed_invoice = invoice
            replay_amount_minor = require_commercial_int(
                "collected_amount_minor",
                existing_metadata.get("collected_amount_minor", 0),
                minimum=0,
            )
            if existing.successful and replay_amount_minor > 0 and invoice.remaining_minor > 0:
                replayed_invoice = self._invoice_lifecycle.record_payment(
                    invoice, amount_minor=min(invoice.remaining_minor, replay_amount_minor)
                )
            return replayed_invoice, existing
        if invoice.status.value in {"draft", "paid", "void", "credited"}:
            raise ValueError("cannot collect invoice from current state")
        amount_minor = invoice.remaining_minor
        if amount_minor <= 0:
            synthetic = CommercialCollectionResult(
                invoice_id=invoice.invoice_id,
                tenant_id=invoice.tenant_id,
                provider_name=self._provider.provider_name(),
                successful=True,
                external_reference=f"noop:{normalized_key}",
                metadata={
                    "owner": "billing.payment_collection",
                    "noop": True,
                    "idempotency_key": normalized_key,
                    "currency": invoice.currency,
                    "collected_amount_minor": 0,
                },
            )
            saved = self._result_store.append(synthetic, idempotency_key=normalized_key)
            if self._metrics is not None:
                self._metrics.inc(
                    tenant_id=invoice.tenant_id,
                    metric_name="billing_collection_attempts_total",
                    amount=1.0,
                    labels={"provider": saved.provider_name, "successful": "true", "noop": "true"},
                )
            return invoice, saved
        attempt = CommercialCollectionAttempt(
            invoice_id=invoice.invoice_id,
            tenant_id=invoice.tenant_id,
            amount_minor=amount_minor,
            currency=invoice.currency,
            provider_name=self._provider.provider_name(),
            idempotency_key=normalized_key,
            attempt_no=require_commercial_int("attempt_no", attempt_no, minimum=1),
            scheduled_at=utc_now(),
            metadata=dict(metadata or {}),
        )
        attempt.validate()
        provider_result = self._provider.collect(attempt)
        self._validate_provider_result(attempt=attempt, result=provider_result)
        result = replace(
            provider_result,
            metadata={
                **dict(provider_result.metadata),
                "owner": "billing.payment_collection",
                "idempotency_key": normalized_key,
                "collected_amount_minor": attempt.amount_minor,
                "currency": invoice.currency,
            },
        )
        saved_result = self._result_store.append(result, idempotency_key=normalized_key)
        updated_invoice = invoice
        if saved_result.successful:
            updated_invoice = self._invoice_lifecycle.record_payment(invoice, amount_minor=attempt.amount_minor)
        if self._metrics is not None:
            self._metrics.inc(
                tenant_id=invoice.tenant_id,
                metric_name="billing_collection_attempts_total",
                amount=1.0,
                labels={"provider": saved_result.provider_name, "successful": str(saved_result.successful).lower()},
            )
        return updated_invoice, saved_result

    def _validate_provider_result(
        self, *, attempt: CommercialCollectionAttempt, result: CommercialCollectionResult
    ) -> None:
        result.validate()
        if str(result.invoice_id) != str(attempt.invoice_id):
            raise ValueError("provider result invoice_id mismatch")
        if str(result.tenant_id) != str(attempt.tenant_id):
            raise ValueError("provider result tenant_id mismatch")
        if str(result.provider_name).strip() != str(attempt.provider_name).strip():
            raise ValueError("provider result provider_name mismatch")


__all__ = ["CANON_BILLING_PAYMENT_COLLECTION", "InMemoryCollectionResultStore", "PaymentCollectionOrchestrator"]
