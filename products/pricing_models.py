from __future__ import annotations

from typing import Any, Mapping

from contracts.product_contract import PricingModel


class FixedPricingModel:
    """Deterministic pricing model: always return a configured offer_id."""

    pricing_model_id = "pricing_fixed@v1"

    def __init__(self, offer_id: str):
        self._offer_id = str(offer_id)

    def choose_offer_id(self, *, user_id: str, tenant_id: str, context: Mapping[str, Any]) -> str:
        return self._offer_id


def resolve_pricing_model(raw: Mapping[str, Any]) -> PricingModel:
    pm = raw.get("pricing_model") if isinstance(raw.get("pricing_model"), dict) else {}
    mid = str(pm.get("id") or "pricing_fixed@v1")
    params = pm.get("params") if isinstance(pm.get("params"), dict) else {}

    if mid == "pricing_fixed@v1":
        offer_id = str(params.get("offer_id") or "basic")
        return FixedPricingModel(offer_id=offer_id)

    # Safe fallback (never crash boot in non-strict environments)
    return FixedPricingModel(offer_id=str(params.get("offer_id") or "basic"))
