"""Recoverable checkout creation through the existing routed PSP and Event Spine.

A PSP-created payment URL is NOT a paid invoice or delivered entitlement.
No second payment state machine: this is immutable provider-binding evidence
used by canonical Billing reconciliation and the one Execution Engine.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from application.ontology import EventFactLifecycleWriter
from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.payment_provider_contract import PaymentCheckoutRequest
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.order import OrderLifecycleStatus

CANON_PHASE18_COMMERCIAL_CHECKOUT_COORDINATOR = True
_SOURCE = "phase18_commercial_checkout"
_FACT = "commercial.checkout_created"


@dataclass(frozen=True)
class CommercialCheckout:
    tenant_id: str
    business_id: str
    order_id: str
    invoice_id: str
    provider_name: str
    external_reference: str
    checkout_url: str
    amount_minor: int
    currency: str
    status: str = "awaiting_payment"


class CommercialCheckoutCoordinator:
    def __init__(self, *, purchase_service: Any, payment_adapter: Any,
                 event_store: Any, idempotency_store: Any) -> None:
        self._purchases = purchase_service
        self._payments = payment_adapter
        self._events = event_store
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="phase18_commercial_checkout", source=_SOURCE,
            id_prefix="commercial-checkout",
        )

    def _saved(self, *, tenant_id: str, business_id: str,
               order_id: str) -> CommercialCheckout | None:
        matches = []
        for event in self._events.iter_events(
            tenant_id=tenant_id, start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE,
        ):
            if event.get("source") != _SOURCE:
                continue
            fact = event.get("payload") or {}
            if (fact.get("business_id") != business_id
                    or fact.get("entity_id") != order_id):
                continue
            if fact.get("fact_type") != _FACT or not isinstance(fact.get("payload"), dict):
                raise RuntimeError("commercial_checkout_durable_fact_invalid")
            row = dict(fact["payload"])
            if (row.get("tenant_id") != tenant_id or row.get("business_id") != business_id
                    or row.get("order_id") != order_id):
                raise RuntimeError("commercial_checkout_durable_scope_invalid")
            try:
                result = CommercialCheckout(**row)
            except TypeError as exc:
                raise RuntimeError("commercial_checkout_durable_payload_invalid") from exc
            if (result.status != "awaiting_payment" or result.amount_minor <= 0
                    or not result.provider_name or not result.external_reference
                    or not _secure_url(result.checkout_url)):
                raise RuntimeError("commercial_checkout_durable_payload_invalid")
            matches.append(result)
        if len(matches) > 1:
            raise RuntimeError("commercial_checkout_duplicate_durable_fact")
        return matches[0] if matches else None

    def open_checkout(self, *, tenant_id: str, business_id: str,
                      order_id: str) -> CommercialCheckout:
        order, link = self._purchases._read(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
        )
        if order.lifecycle_status is not OrderLifecycleStatus.ACTIVE:
            raise ValueError("commercial_checkout_order_not_active")
        invoice = self._purchases.invoices.get(
            tenant_id=tenant_id, business_id=business_id,
            invoice_id=link["invoice_id"],
        )
        if (dict(invoice.metadata).get("order_id") != order_id
                or invoice.tenant_id != tenant_id or invoice.business_id != business_id
                or invoice.total_minor != link["amount_minor"]
                or invoice.currency != link["currency"]):
            raise RuntimeError("commercial_checkout_invoice_binding_invalid")
        invoice.validate()
        existing = self._saved(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
        )
        if existing is not None:
            if (existing.invoice_id != invoice.invoice_id
                    or existing.amount_minor != invoice.total_minor
                    or existing.currency != invoice.currency):
                raise RuntimeError("commercial_checkout_replay_conflict")
            return existing
        if invoice.status is not InvoiceLifecycleStatus.ISSUED or invoice.paid_minor != 0:
            raise ValueError("commercial_checkout_invoice_not_eligible")
        self._purchases._parties(
            tenant_id=tenant_id, business_id=business_id,
            customer_id=link["customer_id"], lead_id=link["lead_id"],
            program_id=link["program_id"],
        )
        req = PaymentCheckoutRequest(
            tenant_id=tenant_id, amount_minor=invoice.total_minor,
            currency=invoice.currency,
            idempotency_key="commercial-checkout:" + order_id,
            customer_reference=link["customer_id"],
            description="Published program",
            metadata={
                "business_id": business_id, "order_id": order_id,
                "invoice_id": invoice.invoice_id, "program_id": link["program_id"],
            },
        )
        session = self._payments.create_checkout(req)
        session = session.normalized_copy()
        if (session.tenant_id != tenant_id or session.amount_minor != invoice.total_minor
                or session.currency != invoice.currency
                or session.status.lower() not in {"pending", "created", "requires_payment"}
                or not _secure_url(session.checkout_url)):
            raise RuntimeError("commercial_checkout_provider_session_invalid")
        created = CommercialCheckout(
            tenant_id=tenant_id, business_id=business_id,
            order_id=order_id, invoice_id=invoice.invoice_id,
            provider_name=session.provider_name,
            external_reference=session.external_reference,
            checkout_url=session.checkout_url,
            amount_minor=session.amount_minor, currency=session.currency,
        )
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=order_id,
            expected_state_token="absent", operation="open_checkout",
            idempotency_key="commercial-checkout:" + order_id,
            fact_type=_FACT, payload=created.__dict__,
            occurred_at_ms=int(time.time() * 1000),
        )
        saved = self._saved(tenant_id=tenant_id, business_id=business_id, order_id=order_id)
        if saved != created:
            raise RuntimeError("commercial_checkout_durable_confirmation_missing")
        return saved

    def provider_observation(self, *, tenant_id: str, business_id: str,
                             order_id: str) -> dict[str, object]:
        """Report provider status WITHOUT mutating invoice/claiming settlement."""
        saved = self._saved(tenant_id=tenant_id, business_id=business_id, order_id=order_id)
        if saved is None:
            raise LookupError("commercial_checkout_not_found")
        status = self._payments.get_payment_status(
            tenant_id=tenant_id, currency=saved.currency,
            provider_name=saved.provider_name, external_reference=saved.external_reference,
        )
        normalized = str(status).lower().strip()
        if normalized not in {"pending", "created", "succeeded", "cancelled", "canceled", "failed"}:
            raise RuntimeError("commercial_checkout_provider_status_invalid")
        return {
            "order_id": order_id, "invoice_id": saved.invoice_id,
            "provider_name": saved.provider_name,
            "provider_reported_status": normalized,
            "invoice_payment_confirmed": False,
            "fulfilment_confirmed": False,
        }


def _secure_url(url: object) -> bool:
    if not isinstance(url, str) or len(url) > 4096:
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (parsed.scheme == "https" and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and not parsed.fragment and not any(ord(c) < 32 for c in url))


__all__ = ["CANON_PHASE18_COMMERCIAL_CHECKOUT_COORDINATOR",
           "CommercialCheckout", "CommercialCheckoutCoordinator"]
