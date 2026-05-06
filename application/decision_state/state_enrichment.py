from __future__ import annotations

from typing import Any, Dict, Tuple

from application.decision_state.state_constraints import (
    apply_causal_constraints,
    apply_price_constraints,
    pricing_constraints_from_state,
)
from application.decision_state.state_world_model_enricher import (
    attach_world_model_explainability,
    enrich_state_with_world_model,
    extract_product_metadata,
)


def _attach_world_model_explainability(state: Any) -> Any:
    return attach_world_model_explainability(state)


def _pricing_constraints_from_state(state: Any) -> Dict[str, Any]:
    return pricing_constraints_from_state(state)


__all__ = [
    "apply_causal_constraints",
    "apply_price_constraints",
    "enrich_state_with_world_model",
    "extract_product_metadata",
    "_attach_world_model_explainability",
    "_pricing_constraints_from_state",
]
