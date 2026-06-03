from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from core.observability.silent import swallow


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reason: str


def check_offer_eligibility(
    *,
    product: Mapping[str, Any],
    tenant_id: str,
    entitlements: Mapping[str, Any],
    payment_status: str | None,
    offer_id: str,
) -> Eligibility:
    # 1) product module flag
    try:
        modules = product.get("modules") or {}
        offers_enabled = bool(modules.get("offers", True))
    except Exception:
        offers_enabled = True
    if not offers_enabled:
        return Eligibility(False, "product_offers_disabled")

    # 2) tenant sanity
    if not str(tenant_id).strip():
        return Eligibility(False, "missing_tenant")

    # 3) simple entitlement guard example
    try:
        if str(offer_id) in ("offer_30", "offer_365") and bool(entitlements.get("pro", False)) is True:
            return Eligibility(False, "already_entitled")
    except Exception:
        swallow(__name__, 'core/offers/eligibility.py')

    # 4) payment status guard
    if payment_status and str(payment_status).lower() in ("failed", "chargeback"):
        return Eligibility(False, "payment_status_block")

    return Eligibility(True, "ok")
