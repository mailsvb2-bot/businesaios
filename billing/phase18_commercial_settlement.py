"""Canonical Billing reconciliation of one externally verified commercial payment.

This module is NOT a second payment registry. Its only financial mutation
calls InvoiceRegistry.record_payment with a durable PSP evidence reference.
It must be called by server-trusted PSP verification, never by a browser,
the raw webhook payload, a chat message, or a model's assertion of payment.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.payment_provider_contract import PaymentCheckoutRequest, PaymentCheckoutSession

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
                 configured_merchant_id: str | Mapping[str, str]) -> None:
        if isinstance(configured_merchant_id, Mapping):
            merchants = dict(configured_merchant_id)
            if (not merchants or any(
                not isinstance(name, str) or not name.strip()
                or not isinstance(merchant, str) or not merchant.strip()
                for name, merchant in merchants.items()
            )):
                raise ValueError("commercial_settlement_merchant_configuration_required")
        else:
            merchant = str(configured_merchant_id or "").strip()
            if not merchant:
                raise ValueError("commercial_settlement_merchant_configuration_required")
            merchants = {"*": merchant}
        if not callable(getattr(payment_verifier, "fetch_settlement_evidence", None)):
            raise TypeError("commercial_settlement_authoritative_provider_required")
        self._purchases = purchases
        self._checkouts = checkouts
        self._verifier = payment_verifier
        self._merchant_ids = merchants

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
        expected_merchant = self._merchant_ids.get(session.provider_name)
        if expected_merchant is None:
            expected_merchant = self._merchant_ids.get("*")
        if not expected_merchant:
            raise RuntimeError("commercial_settlement_provider_not_authorized")
        expected = (
            session.provider_name, expected_merchant, session.external_reference,
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

        if proof.status == "refunded" and invoice.status is InvoiceLifecycleStatus.PAID:
            if not self._purchases.invoices.has_verified_psp_payment_evidence(
                tenant_id=tenant_id, business_id=business_id,
                invoice_id=invoice.invoice_id, evidence_id=proof.evidence_id,
            ):
                raise RuntimeError("commercial_settlement_refunded_without_matching_proof")
            return result(invoice, verified=True)
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




def _minor(value: object) -> int:
    if not isinstance(value, str):
        raise RuntimeError("commercial_psp_amount_untrusted")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise RuntimeError("commercial_psp_amount_invalid") from exc
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise RuntimeError("commercial_psp_amount_invalid")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise RuntimeError("commercial_psp_amount_invalid")
    return int(cents)


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("commercial_psp_response_invalid")
    return value



@dataclass(frozen=True)
class YooKassaCommercialAuthority:
    """One merchant-scoped adapter, settlement verifier and reversal reader.

    create_payment and fetch_payment are trusted server effects, not network
    clients constructed inside Billing. The fetch effect MUST retrieve the
    current payment from the authenticated merchant API and raise on failure.
    """
    merchant_id: str
    create_payment: Callable[..., object]
    fetch_payment: Callable[[str], object]
    checkout_reader: Any
    fetch_refund: Callable[[str], object] | None = None
    refund_reference_reader: Callable[..., str | None] | None = None

    def __post_init__(self) -> None:
        if not self.merchant_id or not self.merchant_id.strip():
            raise ValueError("commercial_yookassa_merchant_required")
        if not callable(self.create_payment) or not callable(self.fetch_payment):
            raise TypeError("commercial_yookassa_sealed_effects_required")

    def create_checkout(self, request: PaymentCheckoutRequest) -> PaymentCheckoutSession:
        req = request.normalized_copy()
        if req.currency != "RUB":
            raise ValueError("commercial_yookassa_rub_only")
        metadata = {**dict(req.metadata), "tenant_id": req.tenant_id}
        required = ("business_id", "order_id", "invoice_id", "program_id")
        if any(not isinstance(metadata.get(k), str) or not metadata[k].strip() for k in required):
            raise ValueError("commercial_yookassa_checkout_binding_required")
        payment = _mapping(self.create_payment(
            amount_minor=req.amount_minor, currency=req.currency,
            customer_id=req.customer_reference, description=req.description,
            idempotency_key=req.idempotency_key, metadata=metadata,
        ))
        if (payment.get("status") != "pending" or payment.get("paid") is not False
                or not isinstance(payment.get("id"), str) or not payment["id"]
                or _minor(_mapping(payment.get("amount")).get("value")) != req.amount_minor
                or _mapping(payment["amount"]).get("currency") != "RUB"
                or any(_mapping(payment.get("metadata")).get(k) != v for k, v in metadata.items())):
            raise RuntimeError("commercial_yookassa_checkout_unverified")
        confirmation = _mapping(payment.get("confirmation"))
        return PaymentCheckoutSession(
            tenant_id=req.tenant_id, provider_name="yookassa",
            external_reference=payment["id"], checkout_url=confirmation.get("confirmation_url", ""),
            status="pending", amount_minor=req.amount_minor, currency="RUB",
        ).normalized_copy()

    def _verified_snapshot(self, *, tenant_id: str, business_id: str,
                           provider_name: str, external_reference: str,
                           order_id: str, invoice_id: str, amount_minor: int,
                           currency: str) -> Mapping[str, Any]:
        if provider_name != "yookassa" or currency != "RUB":
            raise RuntimeError("commercial_yookassa_provider_mismatch")
        snapshot = _mapping(self.fetch_payment(external_reference))
        expected_meta = dict(
            tenant_id=tenant_id, business_id=business_id,
            order_id=order_id, invoice_id=invoice_id,
        )
        md = _mapping(snapshot.get("metadata"))
        amount = _mapping(snapshot.get("amount"))
        if (snapshot.get("id") != external_reference
                or any(md.get(k) != v for k, v in expected_meta.items())
                or amount.get("currency") != currency
                or _minor(amount.get("value")) != amount_minor
                or snapshot.get("status") not in ("pending", "waiting_for_capture", "succeeded", "canceled")):
            raise RuntimeError("commercial_yookassa_provenance_mismatch")
        return snapshot

    def fetch_settlement_evidence(self, *, tenant_id: str, business_id: str,
                                  provider_name: str, external_reference: str) -> ProviderSettlementEvidence:
        checkout = self.checkout_reader(
            tenant_id=tenant_id, business_id=business_id,
            provider_name=provider_name, external_reference=external_reference,
        )
        if checkout is None or checkout.provider_name != provider_name or checkout.external_reference != external_reference:
            raise RuntimeError("commercial_yookassa_checkout_not_bound")
        snapshot = self._verified_snapshot(
            tenant_id=tenant_id, business_id=business_id,
            provider_name=provider_name, external_reference=external_reference,
            order_id=checkout.order_id, invoice_id=checkout.invoice_id,
            amount_minor=checkout.amount_minor, currency=checkout.currency,
        )
        refunded = snapshot.get("refunded_amount")
        if refunded is not None:
            refunded_amount = _mapping(refunded)
            if refunded_amount.get("currency") != "RUB":
                raise RuntimeError("commercial_yookassa_refund_currency_invalid")
            refund_value = refunded_amount.get("value")
            if not isinstance(refund_value, str):
                raise RuntimeError("commercial_yookassa_refund_amount_invalid")
            try:
                refund_decimal = Decimal(refund_value)
            except InvalidOperation as exc:
                raise RuntimeError("commercial_yookassa_refund_amount_invalid") from exc
            if not refund_decimal.is_finite() or refund_decimal < 0 or refund_decimal * 100 > checkout.amount_minor:
                raise RuntimeError("commercial_yookassa_refund_amount_invalid")
        confirmed = (
            snapshot.get("status") == "succeeded"
            and snapshot.get("paid") is True
            and bool(snapshot.get("captured_at"))
        )
        refunded_after_capture = confirmed and refunded is not None and refund_decimal > 0
        return ProviderSettlementEvidence(
            provider_name="yookassa", merchant_id=self.merchant_id,
            external_reference=external_reference, order_id=checkout.order_id,
            invoice_id=checkout.invoice_id, tenant_id=tenant_id, business_id=business_id,
            currency=checkout.currency, amount_minor=checkout.amount_minor,
            status="refunded" if refunded_after_capture else "succeeded" if confirmed else "pending",
            evidence_id="yookassa:payment:" + external_reference,
        )

    def reversal_reader(self, *, tenant_id: str, business_id: str,
                        order_id: str, invoice_id: str) -> bool:
        checkout = self.checkout_reader(
            tenant_id=tenant_id, business_id=business_id,
            order_id=order_id, invoice_id=invoice_id,
        )
        if checkout is None or checkout.order_id != order_id or checkout.invoice_id != invoice_id:
            raise RuntimeError("commercial_yookassa_reversal_checkout_missing")
        snapshot = self._verified_snapshot(
            tenant_id=tenant_id, business_id=business_id,
            provider_name=checkout.provider_name, external_reference=checkout.external_reference,
            order_id=order_id, invoice_id=invoice_id,
            amount_minor=checkout.amount_minor, currency=checkout.currency,
        )
        if self.refund_reference_reader is not None:
            refund_id = self.refund_reference_reader(
                tenant_id=tenant_id, business_id=business_id,
                order_id=order_id, invoice_id=invoice_id,
            )
            if refund_id is not None:
                if not isinstance(refund_id, str) or not refund_id:
                    raise RuntimeError("commercial_yookassa_refund_reference_invalid")
                if self.fetch_refund is None:
                    raise RuntimeError("commercial_yookassa_refund_verifier_missing")
                refund = _mapping(self.fetch_refund(refund_id))
                if (refund.get("id") != refund_id
                        or refund.get("payment_id") != checkout.external_reference
                        or _mapping(refund.get("amount")).get("currency") != checkout.currency
                        or _minor(_mapping(refund["amount"]).get("value")) > checkout.amount_minor
                        or refund.get("status") not in ("pending", "succeeded", "canceled")):
                    raise RuntimeError("commercial_yookassa_refund_binding_invalid")
                if refund["status"] == "succeeded":
                    return True
                if refund["status"] == "pending":
                    return True  # deny access while the refund state is unresolved
        refunded = snapshot.get("refunded_amount")
        if refunded is not None:
            obj = _mapping(refunded)
            if obj.get("currency") != checkout.currency:
                raise RuntimeError("commercial_yookassa_refund_currency_invalid")
            # YooKassa may report a zero refunded amount; never treat unknown as zero.
            value = obj.get("value")
            if value not in ("0.00", "0.0", "0"):
                return True  # conservatively deny on any refund or malformed amount
        return not (snapshot.get("status") == "succeeded"
                    and snapshot.get("paid") is True and bool(snapshot.get("captured_at")))


__all__ = [ "YooKassaCommercialAuthority"]
