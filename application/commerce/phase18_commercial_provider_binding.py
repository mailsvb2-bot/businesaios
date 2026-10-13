"""Construct one merchant commercial boundary over the existing BusinessAIOS owners.

Provider references are resolved from existing durable canonical checkout facts,
not a new PSP/refund/index database. The bound authority supplies the exact
checkout, settlement and reversal capabilities required by the public API.
Only server bootstrap may assemble this object with sealed provider effects.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from application.commerce.phase18_commercial_access import CanonicalPaidProgramAccess
from application.commerce.phase18_commercial_checkout import CommercialCheckoutCoordinator
from billing.phase18_commercial_settlement import CommercialSettlementReconciler
from billing.phase18_yookassa_authority import YooKassaCommercialAuthority

CANON_PHASE18_COMMERCIAL_MERCHANT_BINDING = True


@dataclass(frozen=True)
class CommercialMerchantBundle:
    checkout: CommercialCheckoutCoordinator
    settlement: CommercialSettlementReconciler
    paid_access: CanonicalPaidProgramAccess
    merchant_authority: YooKassaCommercialAuthority


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



def build_sealed_yookassa_commercial_bundle(
    *, purchases: Any, event_store: Any, idempotency_store: Any,
    transport: Any = None,
) -> CommercialMerchantBundle:
    """Opt-in composition with current server-held credentials and HTTP transport.

    Production bootstrap must explicitly select this factory; it is never
    invoked implicitly from a request, webhook or unauthenticated process.
    """
    from functools import partial

    from runtime._internal.effects_clients.yookassa_client import resolve_credentials
    from runtime._internal.effects_clients.yookassa_commercial_merchant import (
        create_merchant_payment,
        fetch_merchant_payment,
    )

    merchant_id, secret, api = resolve_credentials()
    if not merchant_id or not secret or api != "https://api.yookassa.ru":
        raise RuntimeError("commercial_merchant_configuration_missing")
    return build_yookassa_commercial_bundle(
        purchases=purchases, event_store=event_store,
        idempotency_store=idempotency_store, merchant_id=merchant_id,
        sealed_create_payment=partial(create_merchant_payment, transport=transport),
        sealed_fetch_payment=partial(fetch_merchant_payment, transport=transport),
    )


__all__ = ["CANON_PHASE18_COMMERCIAL_MERCHANT_BINDING",
           "CommercialMerchantBundle", "build_yookassa_commercial_bundle",
           "build_sealed_yookassa_commercial_bundle"]
