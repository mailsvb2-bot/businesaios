"""Phase 18 commercial program orders over canonical Customer/Lead/Order/Billing.

This service never accepts buyer/AI-provided prices, payments or fulfilment
claims. No independent commercial database, PSP ledger or execution runtime.
Its read-only readiness result is NOT a completed delivery.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from contracts.customer import CustomerStatus
from contracts.lead import LeadLifecycleStatus
from contracts.order import Order, OrderLifecycleStatus, OrderNotFound
from core.offers.offer_catalog_resolver import OfferCatalogKey

CANON_PHASE18_COMMERCIAL_PURCHASE_COORDINATOR = True
_KEY = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")
_KIND = "commercial_program"
_FORMAT = "commercial_program_v1"


def _required(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ValueError(f"commercial_{name}_invalid")
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"commercial_{name}_invalid")
    return value.strip()


@dataclass(frozen=True)
class PricedProgramOffer:
    catalog_id: str
    offer_id: str
    program_id: str
    currency: str
    amount_minor: int
    fingerprint: str


@dataclass(frozen=True)
class CommercialPurchase:
    order_id: str
    invoice_id: str
    customer_id: str
    lead_id: str
    program_id: str
    offer_id: str
    catalog_id: str
    offer_fingerprint: str
    currency: str
    amount_minor: int
    invoice_status: str
    paid_minor: int


@dataclass(frozen=True)
class CommercialExecutionReadiness:
    order_id: str
    invoice_id: str
    eligible: bool
    reason: str
    invoice_paid: bool
    external_payment_verified: bool


class CommercialProgramPurchaseService:
    """Coordinates existing owners. Runtime OrderStore must use durable backend."""

    def __init__(self, *, leads: Any, customers: Any, programs: Any,
                 offers: Any, orders: Any, invoices: Any) -> None:
        self.leads, self.customers, self.programs = leads, customers, programs
        self.offers, self.orders, self.invoices = offers, orders, invoices

    def _parties(self, *, tenant_id: str, business_id: str, lead_id: str,
                 customer_id: str, program_id: str) -> None:
        lead = self.leads.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)
        if (lead.tenant_id != tenant_id or lead.business_id != business_id
                or lead.lead_id != lead_id or lead.lifecycle_status is not LeadLifecycleStatus.ACTIVE):
            raise ValueError("commercial_lead_inactive_or_unowned")
        record = self.customers.get_customer(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
        )
        customer = record.customer
        if (customer.tenant_id != tenant_id or customer.business_id != business_id
                or customer.customer_id != customer_id or customer.status is not CustomerStatus.ACTIVE):
            raise ValueError("commercial_customer_inactive_or_unowned")
        program = self.programs.get(
            tenant_id=tenant_id, business_id=business_id, program_id=program_id,
        )
        if (program.get("tenant_id") != tenant_id or program.get("business_id") != business_id
                or program.get("id") != program_id or program.get("status") != "active"):
            raise ValueError("commercial_program_unpublished_or_unowned")

    def priced_offer(self, *, tenant_id: str, business_id: str,
                     program_id: str, offer_id: str) -> PricedProgramOffer:
        """Accept only a catalog offer explicitly bound to this program+business."""
        catalog = self.offers.resolve(key=OfferCatalogKey(
            tenant_id=tenant_id, business_id=business_id,
            product_id=program_id, environment="prod",
        ))
        matches = [item for item in catalog.list_offers() if item.offer_id == offer_id]
        if len(matches) != 1:
            raise ValueError("commercial_offer_unavailable")
        item = matches[0]
        meta = dict(item.meta)
        if (meta.get("program_id") != program_id or meta.get("business_id") != business_id
                or (meta.get("tenant_id") is not None and meta["tenant_id"] != tenant_id)):
            raise ValueError("commercial_offer_program_binding_invalid")
        rub = item.base_price_rub
        if type(rub) is not int or not 1 <= rub <= 100_000_000:
            raise ValueError("commercial_offer_price_invalid")
        catalog_id = _required("catalog_id", catalog.id)
        amount = rub * 100
        fingerprint = hashlib.sha256(json.dumps(
            {"catalog_id": catalog_id, "offer_id": offer_id,
             "program_id": program_id, "business_id": business_id,
             "currency": "RUB", "amount_minor": amount,
             "title": item.title, "meta": meta},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return PricedProgramOffer(
            catalog_id=catalog_id, offer_id=offer_id, program_id=program_id,
            currency="RUB", amount_minor=amount, fingerprint=fingerprint,
        )

    @staticmethod
    def _ids(tenant_id: str, business_id: str, key: str) -> tuple[str, str]:
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise ValueError("commercial_idempotency_key_invalid")
        order_id = str(uuid5(NAMESPACE_URL,
            f"businessaios:commercial-order:{tenant_id}:{business_id}:{key}"))
        return order_id, str(uuid5(NAMESPACE_URL, "businessaios:commercial-invoice:" + order_id))

    def _read(self, *, tenant_id: str, business_id: str,
              order_id: str) -> tuple[Order, dict[str, Any]]:
        order = self.orders.get_canonical_order(order_id, tenant_id=tenant_id, business_id=business_id)
        if order.order_kind != _KIND:
            raise ValueError("commercial_order_kind_mismatch")
        link = self.orders.get_order_specialization(
            order_id=order_id, tenant_id=tenant_id, business_id=business_id,
        )
        if (link.get("format") != _FORMAT or
                not all(isinstance(link.get(k), str) and link[k] for k in (
                    "customer_id", "lead_id", "program_id", "offer_id", "catalog_id",
                    "offer_fingerprint", "invoice_id", "currency"
                )) or type(link.get("amount_minor")) is not int or link["amount_minor"] < 1):
            raise RuntimeError("commercial_order_specialization_invalid")
        return order, link

    def prepare_purchase(self, *, tenant_id: str, business_id: str,
                         lead_id: str, customer_id: str, program_id: str,
                         offer_id: str, idempotency_key: str) -> CommercialPurchase:
        scope = {key: _required(key, value) for key, value in (
            ("tenant_id", tenant_id), ("business_id", business_id),
            ("lead_id", lead_id), ("customer_id", customer_id),
            ("program_id", program_id), ("offer_id", offer_id),
        )}
        tenant_id, business_id = scope["tenant_id"], scope["business_id"]
        order_id, invoice_id = self._ids(tenant_id, business_id, idempotency_key)
        requested = {key: scope[key] for key in ("customer_id", "lead_id", "program_id", "offer_id")}
        try:
            order, link = self._read(tenant_id=tenant_id, business_id=business_id,
                                     order_id=order_id)
        except OrderNotFound:
            order, link = None, None
        if order is not None:
            if any(link.get(key) != val for key, val in requested.items()):
                raise ValueError("commercial_idempotency_conflict")
        else:
            self._parties(**{key: scope[key] for key in
                ("tenant_id", "business_id", "lead_id", "customer_id", "program_id")})
            quote = self.priced_offer(tenant_id=tenant_id, business_id=business_id,
                                       program_id=scope["program_id"], offer_id=scope["offer_id"])
            link = {
                "format": _FORMAT, **requested, "invoice_id": invoice_id,
                "catalog_id": quote.catalog_id, "offer_fingerprint": quote.fingerprint,
                "currency": quote.currency, "amount_minor": quote.amount_minor,
            }
            now = int(time.time() * 1000)
            order = self.orders.create_order(
                Order(order_id=order_id, tenant_id=tenant_id, business_id=business_id,
                      order_kind=_KIND, state_key="awaiting_payment",
                      created_at_ms=now, updated_at_ms=now),
                specialization=link,
            )
        if order.lifecycle_status is not OrderLifecycleStatus.ACTIVE:
            raise ValueError("commercial_order_not_active")
        # Recovery after a mid-saga crash uses the original price snapshot.
        metadata = {"order_id": order_id, **requested,
                    "catalog_id": link["catalog_id"],
                    "offer_fingerprint": link["offer_fingerprint"]}
        try:
            invoice = self.invoices.get(
                tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id,
            )
        except LookupError:
            invoice = self.invoices.create(
                business_id=business_id,
                invoice=CommercialInvoiceEnvelope(
                    tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id,
                    currency=link["currency"], subtotal_minor=link["amount_minor"],
                    total_minor=link["amount_minor"], metadata=metadata,
                ),
                idempotency_key="commercial-create:" + order_id,
            )
        if (invoice.tenant_id != tenant_id or invoice.business_id != business_id
                or invoice.invoice_id != invoice_id or dict(invoice.metadata) != metadata
                or invoice.currency != link["currency"]
                or invoice.total_minor != link["amount_minor"]):
            raise RuntimeError("commercial_invoice_order_price_mismatch")
        if invoice.status is InvoiceLifecycleStatus.DRAFT:
            invoice = self.invoices.issue(
                tenant_id=tenant_id, business_id=business_id, invoice_id=invoice_id,
                idempotency_key="commercial-issue:" + order_id,
            )
        return CommercialPurchase(
            order_id=order_id, invoice_id=invoice_id, customer_id=scope["customer_id"],
            lead_id=scope["lead_id"], program_id=scope["program_id"], offer_id=scope["offer_id"],
            catalog_id=link["catalog_id"], offer_fingerprint=link["offer_fingerprint"],
            currency=link["currency"], amount_minor=link["amount_minor"],
            invoice_status=invoice.status.value, paid_minor=invoice.paid_minor,
        )

    def execution_readiness(self, *, tenant_id: str, business_id: str,
                            order_id: str, payment_evidence_reader: Any,
                            reversal_reader: Any) -> CommercialExecutionReadiness:
        """A server-owned verified PSP proof and reversal authority are REQUIRED."""
        tenant_id, business_id, order_id = (_required("tenant_id", tenant_id),
            _required("business_id", business_id), _required("order_id", order_id))
        order, link = self._read(tenant_id=tenant_id, business_id=business_id,
                                  order_id=order_id)
        invoice = self.invoices.get(
            tenant_id=tenant_id, business_id=business_id, invoice_id=link["invoice_id"],
        )
        meta = dict(invoice.metadata)
        if (meta.get("order_id") != order_id
                or any(meta.get(k) != link[k] for k in (
                    "customer_id", "lead_id", "program_id", "offer_id",
                    "catalog_id", "offer_fingerprint"))
                or invoice.tenant_id != tenant_id or invoice.business_id != business_id
                or invoice.total_minor != link["amount_minor"]
                or invoice.currency != link["currency"]):
            raise RuntimeError("commercial_invoice_provenance_invalid")
        invoice.validate()
        paid = (invoice.status is InvoiceLifecycleStatus.PAID
                and type(invoice.paid_minor) is int and invoice.paid_minor == link["amount_minor"])
        if not callable(payment_evidence_reader) or not callable(reversal_reader):
            raise RuntimeError("commercial_payment_authorities_required")
        verified = payment_evidence_reader(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
            invoice_id=invoice.invoice_id, amount_minor=link["amount_minor"],
            currency=link["currency"],
        )
        reverse = reversal_reader(
            tenant_id=tenant_id, business_id=business_id,
            order_id=order_id, invoice_id=invoice.invoice_id,
        )
        if type(verified) is not bool or type(reverse) is not bool:
            raise RuntimeError("commercial_payment_authority_invalid")
        if order.lifecycle_status is not OrderLifecycleStatus.ACTIVE:
            reason = "order_not_active"
        elif not paid:
            reason = "invoice_not_paid"
        elif not verified:
            reason = "psp_not_verified"
        elif reverse:
            reason = "payment_reversed_or_disputed"
        else:
            try:
                self._parties(tenant_id=tenant_id, business_id=business_id,
                              lead_id=link["lead_id"], customer_id=link["customer_id"],
                              program_id=link["program_id"])
            except (LookupError, ValueError):
                reason = "party_or_program_not_active"
            else:
                reason = "ready_for_governed_execution"
        return CommercialExecutionReadiness(
            order_id=order_id, invoice_id=invoice.invoice_id,
            eligible=reason == "ready_for_governed_execution", reason=reason,
            invoice_paid=paid, external_payment_verified=verified,
        )


__all__ = ["CANON_PHASE18_COMMERCIAL_PURCHASE_COORDINATOR",
           "PricedProgramOffer", "CommercialPurchase", "CommercialExecutionReadiness",
           "CommercialProgramPurchaseService"]
