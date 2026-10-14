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


class TelegramStarsCommercialAuthority:
    """Scoped XTR adapter over canonical checkout/InvoiceRegistry ownership.

    The injected callbacks MUST be bound to the existing sealed Telegram Bot API
    and canonical CustomerRegistry, not to user-provided HTTP payloads.
    """
    provider_name = "telegram_stars"

    def __init__(
        self, *, bot_id: str, signing_secret: bytes,
        purchases: Any, checkout_reader: Any, payer_resolver: Any,
        create_invoice_link: Any, read_transactions: Any,
    ) -> None:
        from collections.abc import Callable

        if not _text(bot_id):
            raise ValueError("stars_bot_identity_required")
        if not isinstance(signing_secret, bytes) or len(signing_secret) < 32:
            raise ValueError("stars_signing_secret_invalid")
        for function in (checkout_reader, payer_resolver, create_invoice_link, read_transactions):
            if not isinstance(function, Callable):
                raise TypeError("stars_server_authority_missing")
        self.bot_id = bot_id
        self._secret = signing_secret
        self._purchases = purchases
        self._checkout_reader = checkout_reader
        self._payer = payer_resolver
        self._create_invoice = create_invoice_link
        self._transactions = read_transactions

    def _binding(
        self, *, tenant_id: str, business_id: str,
        order_id: str, invoice_id: str, amount_stars: int,
    ) -> StarsInvoiceBinding:
        _, link = self._purchases._read(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
        )
        if (
            link["invoice_id"] != invoice_id
            or link["amount_minor"] != amount_stars
            or link["currency"] != "XTR"
        ):
            raise RuntimeError("stars_canonical_order_invoice_mismatch")
        user_id = self._payer(
            tenant_id=tenant_id, business_id=business_id,
            customer_id=link["customer_id"],
        )
        binding = StarsInvoiceBinding(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
            invoice_id=invoice_id, customer_id=link["customer_id"],
            telegram_user_id=user_id, amount_stars=amount_stars,
        )
        binding.validate()
        return binding

    def create_checkout(self, request: Any) -> Any:
        from billing.payment_provider_contract import PaymentCheckoutSession

        req = request.normalized_copy()
        if req.currency != "XTR":
            raise ValueError("stars_currency_must_be_xtr")
        meta = dict(req.metadata)
        for field in ("business_id", "order_id", "invoice_id", "program_id"):
            if not _text(meta.get(field)):
                raise ValueError("stars_checkout_scope_required")
        binding = self._binding(
            tenant_id=req.tenant_id, business_id=meta["business_id"],
            order_id=meta["order_id"], invoice_id=meta["invoice_id"],
            amount_stars=req.amount_minor,
        )
        if req.customer_reference != binding.customer_id:
            raise ValueError("stars_checkout_customer_mismatch")
        payload = invoice_payload(binding, secret=self._secret)
        link = self._create_invoice(
            title="Digital program", description=req.description[:255],
            invoice_payload=payload, amount_stars=binding.amount_stars,
        )
        if not isinstance(link, str) or not link.startswith("https://t.me/"):
            raise RuntimeError("stars_checkout_link_unverified")
        return PaymentCheckoutSession(
            tenant_id=req.tenant_id, provider_name=self.provider_name,
            external_reference=payload, checkout_url=link, status="pending",
            amount_minor=req.amount_minor, currency="XTR",
        ).normalized_copy()

    def _checkout_binding(
        self, *, tenant_id: str, business_id: str,
        provider_name: str | None = None,
        external_reference: str | None = None,
        order_id: str | None = None, invoice_id: str | None = None,
    ) -> StarsInvoiceBinding:
        checkout = self._checkout_reader(
            tenant_id=tenant_id, business_id=business_id,
            provider_name=provider_name, external_reference=external_reference,
            order_id=order_id, invoice_id=invoice_id,
        )
        if checkout is None or checkout.provider_name != self.provider_name:
            raise LookupError("stars_checkout_not_found")
        binding = self._binding(
            tenant_id=tenant_id, business_id=business_id,
            order_id=checkout.order_id, invoice_id=checkout.invoice_id,
            amount_stars=checkout.amount_minor,
        )
        if (
            checkout.currency != "XTR"
            or checkout.external_reference != invoice_payload(binding, secret=self._secret)
        ):
            raise RuntimeError("stars_checkout_binding_invalid")
        return binding

    def _receipt(self, binding: StarsInvoiceBinding) -> StarsPaymentReceipt | None:
        transactions = self._transactions()
        if not isinstance(transactions, tuple):
            raise RuntimeError("stars_provider_history_not_authoritative")
        return verified_provider_transaction(
            binding=binding, secret=self._secret, transactions=transactions,
        )

    def fetch_settlement_evidence(
        self, *, tenant_id: str, business_id: str,
        provider_name: str, external_reference: str,
    ) -> Any:
        from billing.phase18_commercial_settlement import ProviderSettlementEvidence

        binding = self._checkout_binding(
            tenant_id=tenant_id, business_id=business_id,
            provider_name=provider_name, external_reference=external_reference,
        )
        receipt = self._receipt(binding)
        evidence = (
            "telegram_stars:payment:" + receipt.charge_id
            if receipt is not None
            else "telegram_stars:pending:" + hashlib.sha256(
                external_reference.encode("utf-8"),
            ).hexdigest()
        )
        if len(evidence) > 256:
            raise RuntimeError("stars_charge_id_oversized")
        return ProviderSettlementEvidence(
            provider_name=self.provider_name, merchant_id=self.bot_id,
            external_reference=external_reference, order_id=binding.order_id,
            invoice_id=binding.invoice_id, tenant_id=tenant_id,
            business_id=business_id, currency="XTR",
            amount_minor=binding.amount_stars,
            status="succeeded" if receipt is not None else "pending",
            evidence_id=evidence,
        )

    def reversal_reader(
        self, *, tenant_id: str, business_id: str,
        order_id: str, invoice_id: str,
    ) -> bool:
        binding = self._checkout_binding(
            tenant_id=tenant_id, business_id=business_id,
            order_id=order_id, invoice_id=invoice_id,
        )
        return self._receipt(binding) is None

    def get_payment_status(
        self, *, tenant_id: str, currency: str,
        provider_name: str, external_reference: str,
    ) -> str:
        # Tenant-only status lookups cannot prove the business/order identity.
        # Settlement verification must go through the scoped reader above.
        if currency != "XTR" or provider_name != self.provider_name:
            raise ValueError("stars_status_provider_invalid")
        return "pending"
