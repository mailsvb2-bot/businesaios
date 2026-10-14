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


def verified_provider_transaction(
    *, binding: StarsInvoiceBinding, secret: bytes,
    transactions: tuple[Mapping[str, Any], ...],
) -> StarsPaymentReceipt | None:
    """Independently verify a *complete* Bot API getStarTransactions snapshot.

    A positive incoming invoice payment must match exactly one original charge.
    A same-charge outgoing transaction represents a refund; any ambiguity
    denies settlement and entitlement. The caller must fetch every page using
    the sealed Telegram client; incomplete history is not acceptable.
    """
    expected = invoice_payload(binding, secret=secret)
    if not isinstance(transactions, tuple):
        raise ValueError("stars_provider_transactions_invalid")
    matched: list[str] = []
    reversed_charges: set[str] = set()
    for row in transactions:
        if not isinstance(row, Mapping):
            raise RuntimeError("stars_provider_transaction_invalid")
        charge = _text(row.get("id"))
        if not charge:
            raise RuntimeError("stars_provider_transaction_invalid")
        receiver = row.get("receiver")
        if receiver is not None:
            if type(row.get("amount")) is not int or row["amount"] >= 0:
                raise RuntimeError("stars_provider_refund_invalid")
            reversed_charges.add(charge)
        source = row.get("source")
        if source is None:
            continue
        if not isinstance(source, Mapping):
            raise RuntimeError("stars_provider_transaction_invalid")
        if source.get("type") != "user" or source.get("transaction_type") != "invoice_payment":
            continue
        payload = _text(source.get("invoice_payload"))
        if not hmac.compare_digest(payload, expected):
            continue
        user = source.get("user")
        if (
            not isinstance(user, Mapping)
            or type(user.get("id")) is not int
            or user["id"] != binding.telegram_user_id
            or type(row.get("amount")) is not int
            or row["amount"] != binding.amount_stars
        ):
            raise RuntimeError("stars_provider_purchase_scope_mismatch")
        matched.append(charge)
    if len(matched) > 1 or len(set(matched)) != len(matched):
        raise RuntimeError("stars_provider_duplicate_invoice_charges")
    if not matched:
        return None
    if matched[0] in reversed_charges:
        return None
    return StarsPaymentReceipt(
        charge_id=matched[0], provider_charge_id="",
        amount_stars=binding.amount_stars, invoice_payload=expected,
    )
