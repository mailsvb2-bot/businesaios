"""Recoverable checkout creation through the existing routed PSP and Event Spine.

A PSP-created payment URL is NOT a paid invoice or delivered entitlement.
No second payment state machine: this is immutable provider-binding evidence
used by canonical Billing reconciliation and the one Execution Engine.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from application.commerce.phase18_commercial_access import CanonicalPaidProgramAccess
from application.ontology import EventFactLifecycleWriter
from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.payment_provider_contract import PaymentCheckoutRequest
from billing.phase18_commercial_settlement import (
    CommercialSettlementReconciler,
    YooKassaCommercialAuthority,
)
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




@dataclass(frozen=True)
class CommercialMerchantBundle:
    checkout: CommercialCheckoutCoordinator
    settlement: CommercialSettlementReconciler
    paid_access: CanonicalPaidProgramAccess
    merchant_authority: Any



def build_yookassa_commercial_bundle(
    *, purchases: Any, event_store: Any, idempotency_store: Any,
    merchant_id: str, sealed_create_payment: Callable[..., object],
    sealed_fetch_payment: Callable[[str], object],
) -> CommercialMerchantBundle:
    """Assembly never creates a second money, checkout, or entitlement owner.

    This only wires capabilities. It does NOT enable merchant payments or
    outbound networking automatically; the caller supplies authenticated
    effects from the existing sealed runtime and its authorized credential
    scope. Missing or ambiguous facts fail closed.
    """
    def canonical_checkout_reader(
        *, tenant_id: str, business_id: str, order_id: str | None = None,
        invoice_id: str | None = None, provider_name: str | None = None,
        external_reference: str | None = None,
    ):
        matched = []
        for order in purchases.orders.list_for_business(
            tenant_id=tenant_id, business_id=business_id,
        ):
            if order.order_kind != "commercial_program":
                continue
            if order_id is not None and order.order_id != order_id:
                continue
            saved = checkout._saved(
                tenant_id=tenant_id, business_id=business_id, order_id=order.order_id,
            )
            if saved is None:
                continue
            if (invoice_id is not None and invoice_id != saved.invoice_id
                    or provider_name is not None and provider_name != saved.provider_name
                    or external_reference is not None
                    and external_reference != saved.external_reference):
                continue
            matched.append(saved)
        if len(matched) > 1:
            raise RuntimeError("commercial_merchant_reference_not_unique")
        return matched[0] if matched else None

    authority = YooKassaCommercialAuthority(
        merchant_id=merchant_id, create_payment=sealed_create_payment,
        fetch_payment=sealed_fetch_payment, checkout_reader=canonical_checkout_reader,
    )
    checkout = CommercialCheckoutCoordinator(
        purchase_service=purchases, payment_adapter=authority,
        event_store=event_store, idempotency_store=idempotency_store,
    )
    settlement = CommercialSettlementReconciler(
        purchases=purchases, checkouts=checkout,
        payment_verifier=authority, configured_merchant_id=merchant_id,
    )
    paid_access = CanonicalPaidProgramAccess(
        purchases=purchases, checkouts=checkout,
        reversal_reader=authority.reversal_reader,
    )
    return CommercialMerchantBundle(
        checkout=checkout, settlement=settlement,
        paid_access=paid_access, merchant_authority=authority,
    )




__all__ = [
           "CommercialMerchantBundle", "build_yookassa_commercial_bundle"]


def build_telegram_stars_commercial_bundle(
    *, purchases: Any, event_store: Any, idempotency_store: Any,
    bot_id: str, signing_secret: bytes, payer_resolver: Callable[..., int],
    sealed_create_invoice_link: Callable[..., str],
    sealed_read_transactions: Callable[[], tuple[dict[str, Any], ...]],
) -> CommercialMerchantBundle:
    """One XTR path through existing checkout, Billing and paid-access owners."""
    from billing.telegram_stars_commercial_proof import TelegramStarsCommercialAuthority

    def canonical_checkout_reader(
        *, tenant_id: str, business_id: str,
        order_id: str | None = None, invoice_id: str | None = None,
        provider_name: str | None = None, external_reference: str | None = None,
    ) -> CommercialCheckout | None:
        matched = []
        for order in purchases.orders.list_for_business(
            tenant_id=tenant_id, business_id=business_id,
        ):
            if order.order_kind != "commercial_program":
                continue
            if order_id is not None and order_id != order.order_id:
                continue
            saved = checkout._saved(
                tenant_id=tenant_id, business_id=business_id, order_id=order.order_id,
            )
            if saved is None:
                continue
            if (
                invoice_id is not None and saved.invoice_id != invoice_id
                or provider_name is not None and saved.provider_name != provider_name
                or external_reference is not None
                and saved.external_reference != external_reference
            ):
                continue
            matched.append(saved)
        if len(matched) > 1:
            raise RuntimeError("stars_checkout_reference_not_unique")
        return matched[0] if matched else None

    authority = TelegramStarsCommercialAuthority(
        bot_id=bot_id, signing_secret=signing_secret, purchases=purchases,
        checkout_reader=canonical_checkout_reader, payer_resolver=payer_resolver,
        create_invoice_link=sealed_create_invoice_link,
        read_transactions=sealed_read_transactions,
    )
    checkout = CommercialCheckoutCoordinator(
        purchase_service=purchases, payment_adapter=authority,
        event_store=event_store, idempotency_store=idempotency_store,
    )
    settlement = CommercialSettlementReconciler(
        purchases=purchases, checkouts=checkout, payment_verifier=authority,
        configured_merchant_id=bot_id,
    )
    access = CanonicalPaidProgramAccess(
        purchases=purchases, checkouts=checkout,
        reversal_reader=authority.reversal_reader,
    )
    return CommercialMerchantBundle(
        checkout=checkout, settlement=settlement,
        paid_access=access, merchant_authority=authority,
    )


class _CanonicalMerchantPortfolio:
    """Provider choice only. One checkout owner, invoice owner and Event Spine."""

    def __init__(self, *, rub_authority: Any, stars_authority: Any) -> None:
        self._by_currency = {"RUB": rub_authority, "XTR": stars_authority}
        self._by_provider = {
            "yookassa": rub_authority, "telegram_stars": stars_authority,
        }
        self.checkout: CommercialCheckoutCoordinator | None = None

    def create_checkout(self, request: PaymentCheckoutRequest) -> Any:
        req = request.normalized_copy()
        provider = self._by_currency.get(req.currency)
        if provider is None:
            raise ValueError("commercial_payment_currency_unsupported")
        return provider.create_checkout(req)

    def fetch_settlement_evidence(self, *, provider_name: str, **scope: Any) -> Any:
        provider = self._by_provider.get(provider_name)
        if provider is None:
            raise RuntimeError("commercial_unknown_payment_provider")
        return provider.fetch_settlement_evidence(provider_name=provider_name, **scope)

    def get_payment_status(self, *, provider_name: str, **scope: Any) -> str:
        provider = self._by_provider.get(provider_name)
        if provider is None:
            raise RuntimeError("commercial_unknown_payment_provider")
        return provider.get_payment_status(provider_name=provider_name, **scope)

    def reversal_reader(
        self, *, tenant_id: str, business_id: str,
        order_id: str, invoice_id: str,
    ) -> bool:
        if self.checkout is None:
            raise RuntimeError("commercial_provider_route_unbound")
        checkout = self.checkout._saved(
            tenant_id=tenant_id, business_id=business_id, order_id=order_id,
        )
        if checkout is None or checkout.invoice_id != invoice_id:
            raise RuntimeError("commercial_provider_checkout_missing")
        provider = self._by_provider.get(checkout.provider_name)
        if provider is None:
            raise RuntimeError("commercial_unknown_payment_provider")
        return provider.reversal_reader(
            tenant_id=tenant_id, business_id=business_id,
            order_id=order_id, invoice_id=invoice_id,
        )


def build_dual_commercial_merchant_bundle(
    *, purchases: Any, event_store: Any, idempotency_store: Any,
    merchant_id: str, sealed_create_payment: Callable[..., object],
    sealed_fetch_payment: Callable[[str], object],
    bot_id: str, signing_secret: bytes, payer_resolver: Callable[..., int],
    sealed_create_invoice_link: Callable[..., str],
    sealed_read_transactions: Callable[[], tuple[dict[str, Any], ...]],
) -> CommercialMerchantBundle:
    """Select fiat/Stars based on immutable invoice currency, never user status."""
    from billing.telegram_stars_commercial_proof import TelegramStarsCommercialAuthority

    def canonical_checkout_reader(
        *, tenant_id: str, business_id: str,
        order_id: str | None = None, invoice_id: str | None = None,
        provider_name: str | None = None, external_reference: str | None = None,
    ) -> CommercialCheckout | None:
        matched = []
        for order in purchases.orders.list_for_business(
            tenant_id=tenant_id, business_id=business_id,
        ):
            if order.order_kind != "commercial_program":
                continue
            if order_id is not None and order_id != order.order_id:
                continue
            saved = checkout._saved(
                tenant_id=tenant_id, business_id=business_id, order_id=order.order_id,
            )
            if saved is None:
                continue
            if (
                invoice_id is not None and saved.invoice_id != invoice_id
                or provider_name is not None and saved.provider_name != provider_name
                or external_reference is not None
                and saved.external_reference != external_reference
            ):
                continue
            matched.append(saved)
        if len(matched) > 1:
            raise RuntimeError("commercial_merchant_reference_not_unique")
        return matched[0] if matched else None

    rub = YooKassaCommercialAuthority(
        merchant_id=merchant_id, create_payment=sealed_create_payment,
        fetch_payment=sealed_fetch_payment, checkout_reader=canonical_checkout_reader,
    )
    stars = TelegramStarsCommercialAuthority(
        bot_id=bot_id, signing_secret=signing_secret,
        purchases=purchases, checkout_reader=canonical_checkout_reader,
        payer_resolver=payer_resolver, create_invoice_link=sealed_create_invoice_link,
        read_transactions=sealed_read_transactions,
    )
    portfolio = _CanonicalMerchantPortfolio(
        rub_authority=rub, stars_authority=stars,
    )
    checkout = CommercialCheckoutCoordinator(
        purchase_service=purchases, payment_adapter=portfolio,
        event_store=event_store, idempotency_store=idempotency_store,
    )
    portfolio.checkout = checkout
    settlement = CommercialSettlementReconciler(
        purchases=purchases, checkouts=checkout, payment_verifier=portfolio,
        configured_merchant_id={
            "yookassa": merchant_id, "telegram_stars": bot_id,
        },
    )
    access = CanonicalPaidProgramAccess(
        purchases=purchases, checkouts=checkout,
        reversal_reader=portfolio.reversal_reader,
    )
    return CommercialMerchantBundle(
        checkout=checkout, settlement=settlement,
        paid_access=access, merchant_authority=portfolio,
    )
