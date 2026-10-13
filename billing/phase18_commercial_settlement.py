"""Canonical Billing reconciliation of one externally verified commercial payment.

This module is NOT a second payment registry. Its only financial mutation
calls InvoiceRegistry.record_payment with a durable PSP evidence reference.
It must be called by server-trusted PSP verification, never by a browser,
the raw webhook payload, a chat message, or a model's assertion of payment.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from billing.commercial_cycle_contract import InvoiceLifecycleStatus

CANON_PHASE18_COMMERCIAL_SETTLEMENT = True


@dataclass(frozen=True)
class ProviderSettlementEvidence:
    provider_name: str
    merchant_id: str
    external_reference: str
    order_id: str
    invoice_id: str
    tenant_id: str
    business_id: str
    currency: str
    amount_minor: int
    status: str
    evidence_id: str


@dataclass(frozen=True)
class CommercialSettlementOutcome:
    order_id: str
    invoice_id: str
    billing_status: str
    paid_minor: int
    total_minor: int
    provider_verified: bool
    evidence_id: str | None


class CommercialSettlementReconciler:
    """Only injected server-owned payment authority may provide evidence."""

    def __init__(self, *, purchases: Any, checkouts: Any, payment_verifier: Any,
                 configured_merchant_id: str) -> None:
        merchant = str(configured_merchant_id or "").strip()
        if not merchant:
            raise ValueError("commercial_settlement_merchant_configuration_required")
        if not callable(getattr(payment_verifier, "fetch_settlement_evidence", None)):
            raise TypeError("commercial_settlement_authoritative_provider_required")
        self._purchases = purchases
        self._checkouts = checkouts
        self._verifier = payment_verifier
        self._merchant_id = merchant

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def reconcile(self, *, tenant_id: str, business_id: str,
                  order_id: str) -> CommercialSettlementOutcome:
        order, link = self._purchases._read(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
        )
        session = self._checkouts._saved(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
        )
        if session is None:
            raise LookupError("commercial_settlement_checkout_missing")
        invoice = self._purchases.invoices.get(
            tenant_id=tenant_id, business_id=business_id,
            invoice_id=link["invoice_id"],
        )
        invoice.validate()
        if (session.tenant_id != tenant_id or session.business_id != business_id
                or session.order_id != order_id or session.invoice_id != invoice.invoice_id
                or session.currency != invoice.currency
                or session.amount_minor != invoice.total_minor
                or invoice.tenant_id != tenant_id or invoice.business_id != business_id
                or dict(invoice.metadata).get("order_id") != order_id
                or invoice.total_minor != link["amount_minor"]
                or invoice.currency != link["currency"]):
            raise RuntimeError("commercial_settlement_checkout_invoice_provenance_invalid")
        proof = self._verifier.fetch_settlement_evidence(
            tenant_id=tenant_id, business_id=business_id,
            provider_name=session.provider_name,
            external_reference=session.external_reference,
        )
        if type(proof) is not ProviderSettlementEvidence:
            raise RuntimeError("commercial_settlement_authoritative_evidence_invalid")
        expected = (
            session.provider_name, self._merchant_id, session.external_reference,
            order_id, invoice.invoice_id, tenant_id, business_id, invoice.currency,
            invoice.total_minor,
        )
        received = (
            proof.provider_name, proof.merchant_id, proof.external_reference,
            proof.order_id, proof.invoice_id, proof.tenant_id, proof.business_id,
            proof.currency, proof.amount_minor,
        )
        if (received != expected or type(proof.amount_minor) is not int
                or proof.amount_minor <= 0 or not proof.evidence_id
                or len(proof.evidence_id) > 256):
            raise RuntimeError("commercial_settlement_provider_provenance_invalid")
        def result(row, *, verified: bool) -> CommercialSettlementOutcome:
            return CommercialSettlementOutcome(
                order_id=order_id, invoice_id=row.invoice_id,
                billing_status=row.status.value, paid_minor=row.paid_minor,
                total_minor=row.total_minor, provider_verified=verified,
                evidence_id=proof.evidence_id,
            )

        if proof.status != "succeeded":
            return result(invoice, verified=False)
        if invoice.status is InvoiceLifecycleStatus.PAID:
            # A previously paid invoice cannot be re-labelled as verified
            # by an unrelated PSP. Canonical evidence must already exist.
            if not self._purchases.invoices.has_verified_psp_payment_evidence(
                tenant_id=tenant_id, business_id=business_id,
                invoice_id=invoice.invoice_id, evidence_id=proof.evidence_id,
            ):
                raise RuntimeError("commercial_settlement_paid_without_matching_proof")
            return result(invoice, verified=True)
        # PSP proof covers the *full* checkout amount. Applying it to an
        # already partially paid invoice would falsely turn mixed/manual money
        # into a verified customer entitlement and could double count receipts.
        if invoice.status is InvoiceLifecycleStatus.PARTIALLY_PAID:
            raise RuntimeError("commercial_settlement_mixed_invoice_payments_not_supported")
        if invoice.status is not InvoiceLifecycleStatus.ISSUED or invoice.paid_minor != 0:
            raise RuntimeError("commercial_settlement_invoice_closed")
        # Same PSP payment identity always resolves to one semantic mutation.
        # Canonical InvoiceRegistry owns idempotency, concurrency and history.
        key = "settlement:" + self._hash(
            tenant_id + ":" + business_id + ":" + invoice.invoice_id + ":" +
            proof.provider_name + ":" + proof.external_reference
        )
        remaining = invoice.total_minor - invoice.paid_minor
        if remaining <= 0:
            # On replay use the *original* requested total. The canonical
            # invoice owner finds the already-written idempotent transition.
            remaining = invoice.total_minor
        updated = self._purchases.invoices.record_payment(
            tenant_id=tenant_id, business_id=business_id,
            invoice_id=invoice.invoice_id, idempotency_key=key,
            amount_minor=remaining,
            event_metadata={
                "evidence_ids": (proof.evidence_id,),
                "provenance": {
                    "authority": "verified_psp",
                    "provider": proof.provider_name,
                    "merchant_digest": self._hash(proof.merchant_id),
                    "external_reference_digest": self._hash(proof.external_reference),
                },
            },
        )
        if (updated.status is not InvoiceLifecycleStatus.PAID
                or updated.paid_minor != updated.total_minor):
            raise RuntimeError("commercial_settlement_incomplete_financial_posting")
        return result(updated, verified=True)


__all__ = ["CANON_PHASE18_COMMERCIAL_SETTLEMENT",
           "ProviderSettlementEvidence", "CommercialSettlementOutcome",
           "CommercialSettlementReconciler"]
