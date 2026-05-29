from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Dict

from application.decision_policy.pricing import allowed_price_band, merge_price_constraints
from config.decision_state_constraints_policy import (
    DEFAULT_DECISION_STATE_CONSTRAINTS_POLICY,
    DecisionStateConstraintsPolicy,
)
from core.ai.causal_guardrails import assess_causal_evidence
from core.observability.throttled_logger import exception_throttled

logger = logging.getLogger(__name__)


def pricing_constraints_from_state(state: Any, policy: DecisionStateConstraintsPolicy = DEFAULT_DECISION_STATE_CONSTRAINTS_POLICY) -> dict[str, Any]:
    economy = getattr(state, "economy", None)
    if not isinstance(economy, dict):
        return {}

    ws = economy.get("pricing_world_state")
    if not isinstance(ws, dict):
        return {}

    out: dict[str, Any] = {}

    try:
        expected_profit = float(ws.get("expected_profit"))
    except Exception:
        expected_profit = None

    try:
        conversion_prob = float(ws.get("conversion_prob_at_price"))
    except Exception:
        conversion_prob = None

    try:
        elasticity = float(ws.get("point_elasticity"))
    except Exception:
        elasticity = None

    if expected_profit is not None and expected_profit < policy.pricing.negative_expected_profit_floor:
        return {
            "max_band": policy.pricing.low_band,
            "mode": policy.pricing.safe_mode,
            "reason": policy.pricing.negative_expected_profit_reason,
            "disallow_aggressive": True,
        }

    if conversion_prob is not None and conversion_prob < policy.pricing.low_conversion_probability_threshold:
        out["max_band"] = policy.pricing.standard_band
        out["reason"] = policy.pricing.low_conversion_reason

    if elasticity is not None and elasticity <= policy.pricing.high_price_sensitivity_threshold:
        out["max_band"] = policy.pricing.standard_band
        out["disallow_aggressive"] = True
        out["reason"] = policy.pricing.high_price_sensitivity_reason

    return out


def apply_causal_constraints(*, state: Any, trace: Any, user_id: str, policy: DecisionStateConstraintsPolicy = DEFAULT_DECISION_STATE_CONSTRAINTS_POLICY) -> Any:
    try:
        economy = getattr(state, "economy", None)
        causal_evidence = economy.get("causal_evidence") if isinstance(economy, dict) else None
        if not isinstance(causal_evidence, dict) or not causal_evidence:
            return state
        trace.try_add_step(
            name="causal_evidence",
            input={},
            output={
                "schema_version": causal_evidence.get("schema_version"),
                "keys": sorted([k for k in causal_evidence.keys() if k != "schema_version"]),
            },
        )
        pricing_evidence = causal_evidence.get("pricing") if isinstance(causal_evidence.get("pricing"), dict) else None
        guardrail = assess_causal_evidence(
            pricing_evidence,
            min_n_days=policy.causal.pricing_min_n_days,
            negative_effect_threshold=policy.causal.negative_effect_threshold,
        )
        trace.try_add_step(
            name="causal_guardrail",
            input={"source": policy.causal.pricing_source},
            output={"level": guardrail.level, "reason": guardrail.reason, "ok": guardrail.ok},
        )
        if isinstance(guardrail.constraints, dict) and guardrail.constraints:
            existing = getattr(state, "price_constraints", None)
            merged = merge_price_constraints(
                base=existing if isinstance(existing, dict) else {},
                override=guardrail.constraints,
                logger=logger,
            )
            return replace(state, price_constraints=merged)
        return state
    except Exception:
        exception_throttled(logger, key=f"{user_id}|causal_guardrails", msg="decision_core: causal evidence processing failed")
        return state


def apply_price_constraints(*, state: Any, trace: Any, user_id: str, policy: DecisionStateConstraintsPolicy = DEFAULT_DECISION_STATE_CONSTRAINTS_POLICY) -> Any:
    try:
        explain_meta = dict(getattr(state, "meta", {}) or {})
        explain_block = dict(explain_meta.get("constraint_explainability") or {})

        pricing_constraints = pricing_constraints_from_state(state, policy=policy)
        if pricing_constraints:
            trace.try_add_step(name="pricing_world_model_constraints", input={}, output=dict(pricing_constraints))
            explain_block["pricing_world_model_constraints"] = dict(pricing_constraints)
            existing = getattr(state, "price_constraints", None)
            merged = merge_price_constraints(
                base=existing if isinstance(existing, dict) else {},
                override=pricing_constraints,
                logger=logger,
            )
            state = replace(state, price_constraints=merged)

        max_band = allowed_price_band(state=state, logger=logger)
        trace.try_add_step(name="constraints", input={}, output={"allowed_price_band": max_band})
        explain_block["allowed_price_band"] = max_band

        behavior = getattr(state, "behavior", None)
        guardrail_violation = False
        if isinstance(behavior, dict):
            guardrail_violation = bool(behavior.get("guardrails_violation") or behavior.get("behavior_guardrails_violation"))

        decision_constraints: dict[str, Any] = {"max_band": str(max_band)}
        if guardrail_violation:
            decision_constraints.update(
                {
                    "mode": policy.pricing.safe_mode,
                    "reason": policy.pricing.behavior_guardrail_reason,
                    "max_band": policy.pricing.low_band,
                    "disallow_offer_prefixes": list(policy.pricing.disallowed_offer_prefixes),
                    "disallow_paywall_first": True,
                    "disallow_aggressive": True,
                }
            )
            explain_block["behavior_guardrail_override"] = dict(decision_constraints)

        existing = getattr(state, "price_constraints", None)
        merged = merge_price_constraints(
            base=existing if isinstance(existing, dict) else {},
            override=decision_constraints,
            logger=logger,
        )

        explain_meta["constraint_explainability"] = explain_block
        return replace(state, price_constraints=merged, meta=explain_meta)
    except Exception:
        exception_throttled(
            logger,
            key=f"{user_id}|merge_constraints",
            msg=f"decision_core: failed to apply price constraints user={user_id}",
        )
        return state
