from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contracts.product_contract import PricingModel


class FixedPricingModel:
    pricing_model_id = "pricing_fixed@v1"

    def __init__(self, offer_id: str):
        self._offer_id = str(offer_id).strip()
        if not self._offer_id:
            raise ValueError("pricing_fixed@v1 requires offer_id")

    def choose_offer_id(self, *, user_id: str, tenant_id: str, context: Mapping[str, Any]) -> str:
        return self._offer_id


class ContextOfferPricingModel:
    pricing_model_id = "pricing_ladder@v1"

    def __init__(self, *, default_offer_id: str, context_field: str, offer_by_value: Mapping[str, object]):
        self._default_offer_id = str(default_offer_id).strip()
        self._context_field = str(context_field).strip()
        self._offer_by_value = {str(k).strip().casefold(): str(v).strip() for k, v in offer_by_value.items()}
        if not self._default_offer_id or not self._context_field:
            raise ValueError("pricing_ladder@v1 requires default_offer_id and context_field")
        if any(not key or not value for key, value in self._offer_by_value.items()):
            raise ValueError("pricing_ladder@v1 offer_by_value contains empty key/value")

    def choose_offer_id(self, *, user_id: str, tenant_id: str, context: Mapping[str, Any]) -> str:
        value = str(context.get(self._context_field) or "").strip().casefold()
        return self._offer_by_value.get(value, self._default_offer_id)


def resolve_pricing_model(raw: Mapping[str, Any]) -> PricingModel:
    pm = raw.get("pricing_model") if isinstance(raw.get("pricing_model"), dict) else {}
    model_id = str(pm.get("id") or "pricing_fixed@v1").strip()
    params = pm.get("params") if isinstance(pm.get("params"), dict) else {}
    if model_id == "pricing_fixed@v1":
        return FixedPricingModel(offer_id=str(params.get("offer_id") or "basic"))
    if model_id == "pricing_ladder@v1":
        mapping = params.get("offer_by_value") if isinstance(params.get("offer_by_value"), dict) else {}
        return ContextOfferPricingModel(
            default_offer_id=str(params.get("default_offer_id") or ""),
            context_field=str(params.get("context_field") or "lifecycle_stage"),
            offer_by_value=mapping,
        )
    raise ValueError(f"unsupported pricing_model id: {model_id}")


__all__ = ["ContextOfferPricingModel", "FixedPricingModel", "resolve_pricing_model"]
