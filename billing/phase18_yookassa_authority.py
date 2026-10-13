"""Business-scoped YooKassa checkout, verified settlement and reversal projection.

Only the existing sealed payment effects may perform provider HTTP operations.
The authority accepts their unmodified, authenticated merchant API response,
never a webhook body, caller-supplied payment state, or browser input.
No invoice, refund, entitlement or duplicate financial storage is introduced.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

from billing.payment_provider_contract import PaymentCheckoutRequest, PaymentCheckoutSession
from billing.phase18_commercial_settlement import ProviderSettlementEvidence

CANON_PHASE18_YOOKASSA_AUTHORITY = True


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
                or _mapping(payment.get("metadata")) != metadata):
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
        confirmed = snapshot.get("status") == "succeeded" and snapshot.get("paid") is True and bool(snapshot.get("captured_at"))
        return ProviderSettlementEvidence(
            provider_name="yookassa", merchant_id=self.merchant_id,
            external_reference=external_reference, order_id=checkout.order_id,
            invoice_id=checkout.invoice_id, tenant_id=tenant_id, business_id=business_id,
            currency=checkout.currency, amount_minor=checkout.amount_minor,
            status="succeeded" if confirmed else "pending",
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


__all__ = ["CANON_PHASE18_YOOKASSA_AUTHORITY", "YooKassaCommercialAuthority"]
