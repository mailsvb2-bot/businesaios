"""Telegram Stars XTR proof boundary for the canonical commercial Billing owner.

This module never books money. Authenticated Telegram transport and a separately
server-trusted receipt verifier must supply evidence; the raw webhook is NEVER
sufficient to mark an invoice paid. The resulting identity may be submitted to
the existing invoice/settlement owner, not to a new Stars ledger.
"""
from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

CANON_TELEGRAM_STARS_COMMERCIAL_PROOF = True


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


@dataclass(frozen=True)
class StarsInvoiceBinding:
    tenant_id: str
    business_id: str
    order_id: str
    invoice_id: str
    customer_id: str
    telegram_user_id: int
    amount_stars: int

    def validate(self) -> None:
        if any(not _text(value) for value in (
            self.tenant_id, self.business_id, self.order_id,
            self.invoice_id, self.customer_id,
        )):
            raise ValueError("stars_scope_required")
        if type(self.telegram_user_id) is not int or self.telegram_user_id <= 0:
            raise ValueError("stars_user_invalid")
        if type(self.amount_stars) is not int or self.amount_stars <= 0:
            raise ValueError("stars_amount_invalid")


def invoice_payload(binding: StarsInvoiceBinding, *, secret: bytes) -> str:
    """Opaque authenticated identifier; no money or PII in Telegram payload."""
    binding.validate()
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("stars_signing_secret_invalid")
    scope = "\x1f".join((
        binding.tenant_id, binding.business_id, binding.order_id,
        binding.invoice_id, binding.customer_id,
        str(binding.telegram_user_id), str(binding.amount_stars),
    ))
    digest = hmac.new(secret, scope.encode("utf-8"), hashlib.sha256).hexdigest()
    return "baios-stars-v1:" + digest


def validate_pre_checkout(
    *, binding: StarsInvoiceBinding, secret: bytes,
    query: Mapping[str, Any],
) -> None:
    """Fail closed before answering a Telegram pre_checkout_query.

    The caller must authenticate Telegram transport independently and must
    only answer ok=True when this validation succeeds.
    """
    expected = invoice_payload(binding, secret=secret)
    if (
        not hmac.compare_digest(_text(query.get("invoice_payload")), expected)
        or query.get("currency") != "XTR"
        or type(query.get("total_amount")) is not int
        or query["total_amount"] != binding.amount_stars
    ):
        raise ValueError("stars_pre_checkout_binding_mismatch")
    user = query.get("from")
    if (
        not isinstance(user, Mapping)
        or type(user.get("id")) is not int
        or user["id"] != binding.telegram_user_id
    ):
        raise ValueError("stars_pre_checkout_payer_mismatch")


@dataclass(frozen=True)
class StarsPaymentReceipt:
    charge_id: str
    provider_charge_id: str
    amount_stars: int
    invoice_payload: str


def verified_receipt(
    *, binding: StarsInvoiceBinding, secret: bytes,
    successful_payment: Mapping[str, Any],
    payer_user_id: int,
    verified_provider_receipt: Mapping[str, Any],
) -> StarsPaymentReceipt:
    """Match webhook against separately verified server-owned PSP evidence.

    verified_provider_receipt MUST be fetched using the authorized Telegram
    bot API by a trusted server effect. Passing the webhook back as this
    argument would violate the contract and is not an acceptable integration.
    """
    expected = invoice_payload(binding, secret=secret)
    if type(payer_user_id) is not int or payer_user_id != binding.telegram_user_id:
        raise ValueError("stars_receipt_payer_mismatch")
    for source in (successful_payment, verified_provider_receipt):
        if (
            not isinstance(source, Mapping)
            or source.get("currency") != "XTR"
            or type(source.get("total_amount")) is not int
            or source["total_amount"] != binding.amount_stars
            or not hmac.compare_digest(_text(source.get("invoice_payload")), expected)
        ):
            raise ValueError("stars_receipt_binding_mismatch")
    charge = _text(successful_payment.get("telegram_payment_charge_id"))
    verified_charge = _text(verified_provider_receipt.get("telegram_payment_charge_id"))
    if not charge or not hmac.compare_digest(charge, verified_charge):
        raise ValueError("stars_charge_unverified")
    verified_user = verified_provider_receipt.get("payer_user_id")
    if type(verified_user) is not int or verified_user != payer_user_id:
        raise ValueError("stars_provider_payer_unverified")
    return StarsPaymentReceipt(
        charge_id=charge,
        provider_charge_id=_text(successful_payment.get("provider_payment_charge_id")),
        amount_stars=binding.amount_stars,
        invoice_payload=expected,
    )
