from __future__ import annotations

from typing import Any

from application.decision_state.state_constraints import (
    apply_causal_constraints,
    apply_price_constraints,
    pricing_constraints_from_state,
)
from application.decision_state.state_world_model_enricher import (
    attach_world_model_explainability,
    enrich_state_with_world_model,
    extract_actor_id,
    extract_product_metadata,
    extract_tenant_id,
)


def _attach_world_model_explainability(state: Any) -> Any:
    return attach_world_model_explainability(state)


def _pricing_constraints_from_state(state: Any) -> dict[str, Any]:
    return pricing_constraints_from_state(state)


__all__ = [
    "apply_causal_constraints",
    "apply_price_constraints",
    "enrich_state_with_world_model",
    "extract_actor_id",
    "extract_product_metadata",
    "extract_tenant_id",
    "_attach_world_model_explainability",
    "_pricing_constraints_from_state",
]
