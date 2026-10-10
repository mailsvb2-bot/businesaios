from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID, uuid5

from billing.commercial_cycle_contract import (
    CommercialCollectionAttempt,
    CommercialCollectionResult,
    require_commercial_int,
    utc_now,
)
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.payment_provider_contract import PaymentProviderContract
from contracts.event_store import canonical_business_event_contract
from core.events.event_types import PAYMENT_FAILED, PAYMENT_SUCCEEDED
from observability.tenant_metrics_registry import TenantMetricsRegistry

CANON_BILLING_PAYMENT_COLLECTION = True
CANON_BILLING_PAYMENT_COLLECTION_EVENT_SPINE_PROJECTION = True
_PAYMENT_COLLECTION_EVENT_NAMESPACE = UUID("7bf0f2f7-bbab-4f8c-9ff1-6fc7b5f4862f")


class _PaymentCollectionEventSpineProjection:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    @staticmethod
    def _event_id(*, tenant_id: str, business_id: str, invoice_id: str, idempotency_key: str) -> str:
        return str(uuid5(
            _PAYMENT_COLLECTION_EVENT_NAMESPACE,
            f"{tenant_id}:{business_id}:{invoice_id}:{idempotency_key}",
        ))

    def _existing(self, *, tenant_id: str, event_id: str, event_type: str) -> dict[str, Any] | None:
        for event in self._events.iter_events(
            tenant_id=str(tenant_id), start_ms=0, event_type=event_type
        ):
            if str(event.get("event_id") or "") == str(event_id):
                return dict(event)
        return None

    def project(
        self,
        *,
        invoice: CommercialInvoiceEnvelope,
        result: CommercialCollectionResult,
        idempotency_key: str,
    ) -> str:
        business_id = str(invoice.business_id or "").strip()
        if not business_id:
            raise RuntimeError("PAYMENT_COLLECTION_DURABLE_BUSINESS_SCOPE_REQUIRED")
        if str(result.tenant_id) != str(invoice.tenant_id):
            raise RuntimeError("PAYMENT_COLLECTION_TENANT_SCOPE_CONFLICT")
        event_type = PAYMENT_SUCCEEDED if result.successful else PAYMENT_FAILED
        event_id = self._event_id(
            tenant_id=result.tenant_id,
            business_id=business_id,
            invoice_id=result.invoice_id,
            idempotency_key=idempotency_key,
        )
        timestamp_ms = int(result.processed_at.timestamp() * 1000)
        metadata = dict(result.metadata)
        actor_id = str(metadata.get("actor_id") or "system").strip() or "system"
        raw_evidence = metadata.get("evidence_ids")
        evidence_ids = [
            str(item).strip()
            for item in (raw_evidence if isinstance(raw_evidence, (list, tuple, set)) else ())
            if str(item).strip()
        ]
        event = {
            "event_id": event_id,
            "tenant_id": result.tenant_id,
            "user_id": actor_id,
            "source": "billing.payment_collection",
            "event_type": event_type,
            "timestamp_ms": timestamp_ms,
            "decision_id": str(metadata.get("decision_id") or "").strip() or None,
            "correlation_id": str(metadata.get("correlation_id") or "").strip() or None,
            "payload": {
                "schema_version": 1,
                "business_id": business_id,
                "actor_id": actor_id,
                "agent_id": str(metadata.get("agent_id") or "").strip() or None,
                "occurred_at_ms": timestamp_ms,
                "recorded_at_ms": timestamp_ms,
                "causation_id": str(
                    metadata.get("causation_id") or metadata.get("action_intent_id") or ""
                ).strip() or None,
                "evidence_ids": evidence_ids,
                "invoice_id": result.invoice_id,
                "subscription_id": invoice.subscription_id,
                "successful": bool(result.successful),
                "provider_name": result.provider_name,
                "external_reference": result.external_reference,
                "failure_reason": result.failure_reason,
                "currency": str(metadata.get("currency") or invoice.currency).upper(),
                "collected_amount_minor": int(metadata.get("collected_amount_minor") or 0),
                "idempotency_key": idempotency_key,
            },
        }
        existing = self._existing(
            tenant_id=result.tenant_id,
            event_id=event_id,
            event_type=event_type,
        )
        if existing is not None:
            if canonical_business_event_contract(existing) != canonical_business_event_contract(event):
                raise RuntimeError("PAYMENT_COLLECTION_EVENT_SPINE_CONFLICT")
            return event_id
        try:
            self._events.append_event(event)
        except Exception:
            existing = self._existing(
                tenant_id=result.tenant_id,
                event_id=event_id,
                event_type=event_type,
            )
            if existing is None or canonical_business_event_contract(existing) != canonical_business_event_contract(event):
                raise
            return event_id
        existing = self._existing(
            tenant_id=result.tenant_id,
            event_id=event_id,
            event_type=event_type,
        )
        if existing is None:
            raise RuntimeError("PAYMENT_COLLECTION_EVENT_SPINE_APPEND_NOT_DURABLE")
        if canonical_business_event_contract(existing) != canonical_business_event_contract(event):
            raise RuntimeError("PAYMENT_COLLECTION_EVENT_SPINE_CONFLICT")
        return event_id



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
        event_store: Any | None = None,
    ) -> None:
        self._provider = provider
        self._invoice_lifecycle = invoice_lifecycle or InvoiceLifecycleService()
        self._result_store = result_store or InMemoryCollectionResultStore()
        self._metrics = metrics
        self._collection_events = None if event_store is None else _PaymentCollectionEventSpineProjection(event_store)

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
            self._project_collection_event(invoice=invoice, result=existing, idempotency_key=normalized_key)
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
            self._project_collection_event(invoice=invoice, result=saved, idempotency_key=normalized_key)
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
        self._project_collection_event(
            invoice=invoice,
            result=saved_result,
            idempotency_key=normalized_key,
        )
        return updated_invoice, saved_result

    def _project_collection_event(
        self,
        *,
        invoice: CommercialInvoiceEnvelope,
        result: CommercialCollectionResult,
        idempotency_key: str,
    ) -> str | None:
        if self._collection_events is None:
            return None
        return self._collection_events.project(
            invoice=invoice,
            result=result,
            idempotency_key=idempotency_key,
        )

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


__all__ = ["CANON_BILLING_PAYMENT_COLLECTION", "CANON_BILLING_PAYMENT_COLLECTION_EVENT_SPINE_PROJECTION", "InMemoryCollectionResultStore", "PaymentCollectionOrchestrator"]
