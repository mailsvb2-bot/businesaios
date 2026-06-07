from __future__ import annotations

from typing import Any

from application.decision_state.state_enrichment import (
    apply_causal_constraints,
    apply_price_constraints,
    enrich_state_with_world_model,
)
from application.decision_state.world_model_metadata import extract_world_model_metadata
from core.decision.ai_decision_trace import TraceBuilder


def replay_state_against_world_model(
    *,
    state: Any,
    world_model: Any | None,
) -> dict[str, Any]:
    """
    Canonical replay helper:
    - re-enriches state
    - re-applies causal constraints
    - re-applies price constraints
    - returns explainability snapshot for audit/comparison
    """
    trace = TraceBuilder(
        user_id=str(getattr(state, "user_id", "unknown") or "unknown"),
        correlation_id=None,
    )

    replayed = enrich_state_with_world_model(state=state, world_model=world_model)
    replayed = apply_causal_constraints(
        state=replayed,
        trace=trace,
        user_id=str(getattr(replayed, "user_id", "unknown") or "unknown"),
    )
    replayed = apply_price_constraints(
        state=replayed,
        trace=trace,
        user_id=str(getattr(replayed, "user_id", "unknown") or "unknown"),
    )

    meta = dict(getattr(replayed, "meta", {}) or {})
    economy = dict(getattr(replayed, "economy", {}) or {})
    price_constraints = getattr(replayed, "price_constraints", None)

    return {
        "world_model_meta": extract_world_model_metadata(state=replayed),
        "world_model_explainability": dict(meta.get("world_model_explainability") or {}),
        "constraint_explainability": dict(meta.get("constraint_explainability") or {}),
        "price_constraints": dict(price_constraints or {}) if isinstance(price_constraints, dict) else {},
        "predicted_ltv": economy.get("predicted_ltv"),
        "pricing_world_state": dict(economy.get("pricing_world_state") or {}) if isinstance(economy.get("pricing_world_state"), dict) else {},
        "trace": trace.build(decision_id="world_model_replay").to_dict(),
    }
