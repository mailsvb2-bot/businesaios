from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True

from dataclasses import asdict
from typing import Any

from runtime.boot import MarketContext, WorldModelInput

from runtime.platform.economics.world_model_store import WorldModelStorePort
from bootstrap.canonical_decision_world_model_resolvers import (
    resolve_float,
    resolve_product_id,
    resolve_tenant_id,
    safe_dict,
    timestamp_to_utc_datetime,
)


def build_market_context(*, state: Any, tenant_id: str, product_id: str, product: dict[str, Any]) -> MarketContext:
    session = safe_dict(getattr(state, "session", None))
    meta = safe_dict(getattr(state, "meta", None))
    dt = timestamp_to_utc_datetime(int(getattr(state, "timestamp_ms", 0) or 0))
    return MarketContext(
        tenant_id=str(tenant_id),
        product_id=str(product_id),
        currency=str(product.get("currency") or "USD"),
        channel=str(session.get("channel") or meta.get("channel") or "unknown"),
        geo=str(session.get("geo") or meta.get("geo") or "unknown"),
        device=str(session.get("device") or meta.get("device") or "unknown"),
        dow=int(dt.weekday()) if dt is not None else None,
        hour=int(dt.hour) if dt is not None else None,
    )


def enrich_pricing(*, state: Any, product: dict[str, Any], economy: dict[str, Any], meta: dict[str, Any], store: WorldModelStorePort):
    tenant_id = resolve_tenant_id(state=state, product=product)
    product_id = resolve_product_id(product=product)
    current_price = resolve_float(
        product.get("current_price"),
        product.get("price"),
        product.get("offer_price"),
        product.get("price_amount"),
        economy.get("current_price"),
        economy.get("price"),
    )
    marginal_cost = resolve_float(
        product.get("marginal_cost"),
        product.get("unit_cost"),
        economy.get("marginal_cost"),
        economy.get("unit_cost"),
    )
    if not tenant_id or not product_id or current_price is None:
        out = dict(meta)
        out["pricing_world_model_skipped"] = True
        if not tenant_id:
            out["pricing_world_model_skip_reason"] = "missing_or_noncanonical_tenant"
        elif not product_id:
            out["pricing_world_model_skip_reason"] = "missing_product_id"
        else:
            out["pricing_world_model_skip_reason"] = "missing_price"
        return dict(economy), out

    from bootstrap.world_model_builder import load_pricing_world_model_with_metadata_for

    pricing_model, pricing_meta = load_pricing_world_model_with_metadata_for(
        tenant_id=tenant_id,
        product_id=product_id,
        store=store,
    )
    inp = WorldModelInput(
        context=build_market_context(state=state, tenant_id=tenant_id, product_id=product_id, product=product),
        current_price=float(current_price),
        marginal_cost=float(marginal_cost) if marginal_cost is not None else None,
    )
    pricing_state = pricing_model.build(inp)
    out_economy = dict(economy)
    out_meta = dict(meta)
    out_economy["pricing_world_state"] = asdict(pricing_state)
    out_economy["world_model_source"] = "canonical"
    out_meta["pricing_world_model"] = pricing_meta["pricing_world_model"]
    out_meta["pricing_world_model_version"] = pricing_meta["pricing_world_model_version"]
    out_meta["pricing_world_model_hash"] = pricing_meta["pricing_world_model_hash"]
    out_meta["pricing_world_model_origin"] = pricing_meta["pricing_world_model_origin"]
    return out_economy, out_meta
