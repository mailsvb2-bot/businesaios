from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Dict, Tuple

from application.decision_state.world_model_metadata import summarize_pricing_world_state
from core.observability.throttled_logger import exception_throttled

logger = logging.getLogger(__name__)


def extract_product_metadata(state: Any) -> Tuple[Dict[str, Any], str | None, str | None, str | None]:
    try:
        product = dict(getattr(state, "product", {}) or {})
    except Exception:
        product = {}
    product_id = str(product.get("product_id") or "").strip() or None
    domain = str(product.get("domain") or "").strip() or None
    product_version = str(product.get("product_version") or "").strip() or None
    return product, product_id, domain, product_version


def attach_world_model_explainability(state: Any) -> Any:
    meta = dict(getattr(state, "meta", {}) or {})
    economy = dict(getattr(state, "economy", {}) or {})

    explain = dict(meta.get("world_model_explainability") or {})
    if "predicted_ltv" in economy:
        explain["predicted_ltv"] = economy.get("predicted_ltv")

    pricing_summary = summarize_pricing_world_state(state=state)
    if pricing_summary:
        explain["pricing_world_state_summary"] = pricing_summary

    meta["world_model_explainability"] = explain
    return replace(state, meta=meta)


def enrich_state_with_world_model(*, state: Any, world_model: Any | None) -> Any:
    if world_model is None:
        return state

    enrich_fn = getattr(world_model, "enrich_state", None)
    if not callable(enrich_fn):
        exception_throttled(
            logger,
            key=f'{getattr(state, "user_id", "unknown")}|world_model_contract',
            msg="decision_core: non-canonical world model ignored (missing enrich_state)",
        )
        return attach_world_model_explainability(state)

    try:
        enriched = enrich_fn(state)
    except Exception:
        exception_throttled(
            logger,
            key=f'{getattr(state, "user_id", "unknown")}|canonical_world_model',
            msg="decision_core: canonical world model enrichment failed",
        )
        return attach_world_model_explainability(state)
    return attach_world_model_explainability(enriched)
