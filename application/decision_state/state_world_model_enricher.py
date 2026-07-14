from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from application.decision_state.world_model_metadata import summarize_pricing_world_state
from core.observability.throttled_logger import exception_throttled
from core.tenancy.normalization import normalize_tenant_id

logger = logging.getLogger(__name__)


def _mapping_attr(state: Any, name: str) -> dict[str, Any]:
    try:
        value = getattr(state, name, {}) or {}
        return dict(value) if isinstance(value, dict) else {}
    except Exception:
        return {}


def extract_tenant_id(state: Any) -> str | None:
    """Extract the non-placeholder tenant isolation key used by the gate."""

    product_metadata = _mapping_attr(state, "product_metadata")
    tenant_id = normalize_tenant_id(
        product_metadata.get("tenant_id")
        or getattr(state, "tenant_id", "")
    )
    return tenant_id or None


def extract_actor_id(state: Any) -> str | None:
    """Extract the canonical acting identity without reusing a target user."""

    user = _mapping_attr(state, "user")
    for candidate in (
        getattr(state, "user_id", None),
        user.get("actor_id"),
        user.get("user_id"),
        user.get("id"),
        user.get("account_id"),
    ):
        actor_id = str(candidate or "").strip()
        if actor_id and actor_id.casefold() not in {"unknown", "none", "null"}:
            return actor_id
    return None


def extract_product_metadata(state: Any) -> tuple[dict[str, Any], str | None, str | None, str | None]:
    product = _mapping_attr(state, "product")
    product_metadata = _mapping_attr(state, "product_metadata")
    merged = {**product_metadata, **product}
    product_id = str(merged.get("product_id") or "").strip() or None
    domain = str(merged.get("domain") or "").strip() or None
    product_version = str(merged.get("product_version") or "").strip() or None
    return merged, product_id, domain, product_version


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
