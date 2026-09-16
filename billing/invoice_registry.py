from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime
from typing import Any

from application.ontology import EventFactLifecycleWriter
from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_contract import IdempotencyStore

CANON_BILLING_INVOICE_PROJECTOR = True
CANON_BILLING_INVOICE_LIFECYCLE_OWNER = True
INVOICE_SCHEMA_VERSION = 1

INVOICE_CREATED = "invoice.created"
INVOICE_ISSUED = "invoice.issued"
INVOICE_PAYMENT_RECORDED = "invoice.payment_recorded"
INVOICE_VOIDED = "invoice.voided"
INVOICE_CREDITED = "invoice.credited"
INVOICE_UNCOLLECTIBLE = "invoice.uncollectible"
INVOICE_FACT_TYPES = frozenset(
    {
        INVOICE_CREATED,
        INVOICE_ISSUED,
        INVOICE_PAYMENT_RECORDED,
        INVOICE_VOIDED,
        INVOICE_CREDITED,
        INVOICE_UNCOLLECTIBLE,
    }
)


class InvoiceNotFound(LookupError):
    pass


class InvoiceHistoryInvariantViolation(RuntimeError):
    pass


def _time_ms(value: int | None) -> int:
    return int(time.time() * 1000) if value is None else max(0, int(value))


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _datetime(value: object, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise InvoiceHistoryInvariantViolation(f"invoice history has invalid {field_name}") from exc
    if parsed.tzinfo is None:
        raise InvoiceHistoryInvariantViolation(f"invoice history has naive {field_name}")
    return parsed


def _payload(invoice: CommercialInvoiceEnvelope) -> dict[str, object]:
    invoice.validate()
    return {
        "schema_version": INVOICE_SCHEMA_VERSION,
        "business_id": invoice.business_id,
        "subscription_id": invoice.subscription_id,
        "currency": invoice.currency,
        "subtotal_minor": invoice.subtotal_minor,
        "tax_minor": invoice.tax_minor,
        "total_minor": invoice.total_minor,
        "status": invoice.status.value,
        "issued_at": _iso(invoice.issued_at),
        "due_at": _iso(invoice.due_at),
        "paid_minor": invoice.paid_minor,
        "metadata": dict(invoice.metadata),
    }


def _from_payload(*, tenant_id: str, business_id: str, invoice_id: str, payload: dict[str, object]) -> CommercialInvoiceEnvelope:
    if payload.get("schema_version") != INVOICE_SCHEMA_VERSION:
        raise InvoiceHistoryInvariantViolation("invoice history has unsupported schema_version")
    if str(payload.get("business_id") or "") != str(business_id):
        raise InvoiceHistoryInvariantViolation("invoice history business_id does not match fact scope")
    try:
        status = InvoiceLifecycleStatus(str(payload.get("status") or ""))
        invoice = CommercialInvoiceEnvelope(
            tenant_id=str(tenant_id),
            invoice_id=str(invoice_id),
            business_id=str(business_id),
            subscription_id=(str(payload["subscription_id"]) if payload.get("subscription_id") is not None else None),
            currency=str(payload.get("currency") or ""),
            subtotal_minor=int(payload.get("subtotal_minor") or 0),
            tax_minor=int(payload.get("tax_minor") or 0),
            total_minor=int(payload.get("total_minor") or 0),
            status=status,
            issued_at=_datetime(payload.get("issued_at"), field_name="issued_at"),
            due_at=_datetime(payload.get("due_at"), field_name="due_at"),
            paid_minor=int(payload.get("paid_minor") or 0),
            metadata=dict(payload.get("metadata") or {}),
        )
        invoice.validate()
        return invoice
    except InvoiceHistoryInvariantViolation:
        raise
    except (TypeError, ValueError) as exc:
        raise InvoiceHistoryInvariantViolation("invoice history has invalid snapshot") from exc


def _immutable_key(invoice: CommercialInvoiceEnvelope) -> tuple[object, ...]:
    return (
        invoice.tenant_id,
        invoice.invoice_id,
        invoice.business_id,
        invoice.subscription_id,
        invoice.currency,
        invoice.subtotal_minor,
        invoice.tax_minor,
        invoice.total_minor,
    )


class InvoiceProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, invoice_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in INVOICE_FACT_TYPES or (invoice_id is not None and entity_id != str(invoice_id)):
                continue
            rows.append(
                {
                    "fact_id": str(event.get("event_id") or ""),
                    "fact_type": fact_type,
                    "entity_id": entity_id,
                    "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                    "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                    "append_order": append_order,
                    "payload": dict(envelope.get("payload") or {}),
                }
            )
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, invoice_id: str) -> CommercialInvoiceEnvelope:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)
        if not facts:
            raise InvoiceNotFound(f"invoice not found: {invoice_id}")
        created = [row for row in facts if row["fact_type"] == INVOICE_CREATED]
        if len(created) != 1 or facts[0] is not created[0]:
            raise InvoiceHistoryInvariantViolation("invoice history must begin with exactly one create fact")
        current = _from_payload(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id, payload=dict(created[0]["payload"]))
        for row in facts[1:]:
            if row["fact_type"] == INVOICE_CREATED:
                raise InvoiceHistoryInvariantViolation("invoice history contains multiple create facts")
            candidate = _from_payload(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id, payload=dict(row["payload"]))
            if _immutable_key(candidate) != _immutable_key(current):
                raise InvoiceHistoryInvariantViolation("invoice immutable identity or money fields were rewritten")
            lifecycle = InvoiceLifecycleService()
            try:
                if row["fact_type"] == INVOICE_ISSUED:
                    expected = lifecycle.issue(current, issued_at=candidate.issued_at, due_at=candidate.due_at)
                elif row["fact_type"] == INVOICE_PAYMENT_RECORDED:
                    delta = candidate.paid_minor - current.paid_minor
                    if delta <= 0:
                        raise ValueError("payment transition must increase paid_minor")
                    expected = lifecycle.record_payment(current, amount_minor=delta)
                elif row["fact_type"] == INVOICE_VOIDED:
                    expected = lifecycle.void(current)
                elif row["fact_type"] == INVOICE_CREDITED:
                    expected = lifecycle.credit(current)
                elif row["fact_type"] == INVOICE_UNCOLLECTIBLE:
                    expected = lifecycle.mark_uncollectible(current)
                else:
                    raise ValueError("unknown invoice fact type")
            except ValueError as exc:
                raise InvoiceHistoryInvariantViolation("invoice history contains illegal lifecycle transition") from exc
            if candidate != expected:
                raise InvoiceHistoryInvariantViolation("invoice fact snapshot does not match canonical lifecycle transition")
            current = candidate
        return current

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[CommercialInvoiceEnvelope, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, invoice_id=value) for value in ids)


class InvoiceRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = InvoiceProjector(event_store)
        self._lifecycle = InvoiceLifecycleService()
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="invoice_fact",
            source="invoice_registry",
            id_prefix="invoice",
        )

    @staticmethod
    def _state_token(invoice: CommercialInvoiceEnvelope) -> str:
        return "|".join(
            (
                invoice.status.value,
                str(invoice.paid_minor),
                _iso(invoice.issued_at) or "",
                _iso(invoice.due_at) or "",
                repr(sorted(dict(invoice.metadata).items())),
            )
        )

    @staticmethod
    def _business_id(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("business_id is required")
        return normalized

    def create(
        self,
        *,
        business_id: str,
        invoice: CommercialInvoiceEnvelope,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> CommercialInvoiceEnvelope:
        invoice.validate()
        business_id = self._business_id(business_id)
        if invoice.business_id and str(invoice.business_id).strip() != business_id:
            raise ValueError("invoice business_id does not match canonical fact scope")
        if not invoice.business_id:
            invoice = replace(invoice, business_id=business_id)
        payload = _payload(invoice)
        try:
            current = self._projector.get(
                tenant_id=invoice.tenant_id, business_id=business_id, invoice_id=invoice.invoice_id
            )
        except InvoiceNotFound:
            current = None
        if current is not None:
            if _payload(current) != payload:
                raise ValueError("invoice already exists with different canonical state")
            self._writer.repair_existing(
                tenant_id=invoice.tenant_id,
                business_id=business_id,
                entity_id=invoice.invoice_id,
                operation="create",
                idempotency_key=idempotency_key,
                fact_type=INVOICE_CREATED,
                payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=invoice.tenant_id,
            business_id=business_id,
            entity_id=invoice.invoice_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=INVOICE_CREATED,
            payload=payload,
            occurred_at_ms=_time_ms(occurred_at_ms),
        )
        return self.get(tenant_id=invoice.tenant_id, business_id=business_id, invoice_id=invoice.invoice_id)

    def _transition(
        self,
        *,
        business_id: str,
        current: CommercialInvoiceEnvelope,
        candidate: CommercialInvoiceEnvelope,
        idempotency_key: str,
        operation: str,
        fact_type: str,
        occurred_at_ms: int | None,
    ) -> CommercialInvoiceEnvelope:
        if _immutable_key(candidate) != _immutable_key(current):
            raise ValueError("invoice transition cannot rewrite immutable identity or money fields")
        if candidate == current:
            return current
        self._writer.append_transition_once(
            tenant_id=current.tenant_id,
            business_id=business_id,
            entity_id=current.invoice_id,
            expected_state_token=self._state_token(current),
            operation=operation,
            idempotency_key=idempotency_key,
            fact_type=fact_type,
            payload=_payload(candidate),
            occurred_at_ms=_time_ms(occurred_at_ms),
        )
        return self.get(tenant_id=current.tenant_id, business_id=business_id, invoice_id=current.invoice_id)

    def issue(self, *, tenant_id: str, business_id: str, invoice_id: str, idempotency_key: str, issued_at: datetime | None = None, due_at: datetime | None = None, occurred_at_ms: int | None = None) -> CommercialInvoiceEnvelope:
        business_id = self._business_id(business_id)
        current = self.get(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)
        candidate = self._lifecycle.issue(current, issued_at=issued_at, due_at=due_at)
        return self._transition(business_id=business_id, current=current, candidate=candidate, idempotency_key=idempotency_key, operation="issue", fact_type=INVOICE_ISSUED, occurred_at_ms=occurred_at_ms)

    def record_payment(self, *, tenant_id: str, business_id: str, invoice_id: str, idempotency_key: str, amount_minor: int, paid_at: datetime | None = None, occurred_at_ms: int | None = None) -> CommercialInvoiceEnvelope:
        business_id = self._business_id(business_id)
        current = self.get(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)
        candidate = self._lifecycle.record_payment(current, amount_minor=amount_minor, paid_at=paid_at)
        return self._transition(business_id=business_id, current=current, candidate=candidate, idempotency_key=idempotency_key, operation="record_payment", fact_type=INVOICE_PAYMENT_RECORDED, occurred_at_ms=occurred_at_ms)

    def void(self, *, tenant_id: str, business_id: str, invoice_id: str, idempotency_key: str, occurred_at_ms: int | None = None) -> CommercialInvoiceEnvelope:
        business_id = self._business_id(business_id)
        current = self.get(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)
        candidate = self._lifecycle.void(current)
        return self._transition(business_id=business_id, current=current, candidate=candidate, idempotency_key=idempotency_key, operation="void", fact_type=INVOICE_VOIDED, occurred_at_ms=occurred_at_ms)

    def credit(self, *, tenant_id: str, business_id: str, invoice_id: str, idempotency_key: str, occurred_at_ms: int | None = None) -> CommercialInvoiceEnvelope:
        business_id = self._business_id(business_id)
        current = self.get(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)
        candidate = self._lifecycle.credit(current)
        return self._transition(business_id=business_id, current=current, candidate=candidate, idempotency_key=idempotency_key, operation="credit", fact_type=INVOICE_CREDITED, occurred_at_ms=occurred_at_ms)

    def mark_uncollectible(self, *, tenant_id: str, business_id: str, invoice_id: str, idempotency_key: str, occurred_at_ms: int | None = None) -> CommercialInvoiceEnvelope:
        business_id = self._business_id(business_id)
        current = self.get(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)
        candidate = self._lifecycle.mark_uncollectible(current)
        return self._transition(business_id=business_id, current=current, candidate=candidate, idempotency_key=idempotency_key, operation="mark_uncollectible", fact_type=INVOICE_UNCOLLECTIBLE, occurred_at_ms=occurred_at_ms)

    def get(self, *, tenant_id: str, business_id: str, invoice_id: str) -> CommercialInvoiceEnvelope:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[CommercialInvoiceEnvelope, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = [
    "CANON_BILLING_INVOICE_LIFECYCLE_OWNER",
    "CANON_BILLING_INVOICE_PROJECTOR",
    "INVOICE_FACT_TYPES",
    "INVOICE_SCHEMA_VERSION",
    "InvoiceHistoryInvariantViolation",
    "InvoiceNotFound",
    "InvoiceProjector",
    "InvoiceRegistry",
]
