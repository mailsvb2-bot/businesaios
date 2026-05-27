from __future__ import annotations

"""Causal guardrails (evidence -> deterministic constraints).

This module is intentionally conservative.
It does NOT decide actions. It only produces constraints and risk signals
that DecisionCore may include in DecisionTrace and (optionally) apply as
soft safety gates.

Inputs:
- causal_evidence: a dict produced by core.causal.evidence.*
Outputs:
- dict suitable for merging into WorldState.price_constraints or state.meta

No side effects.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from config.causal_guardrails_policy import (
    DEFAULT_CAUSAL_GUARDRAILS_POLICY,
    CausalGuardrailsPolicy,
)

Json = Dict[str, Any]


@dataclass(frozen=True)
class CausalGuardrailDecision:
    ok: bool
    level: str  # info|warn|block
    reason: str
    constraints: Json


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def assess_causal_evidence(
    causal_evidence: Json | None,
    *,
    min_n_days: int | None = None,
    negative_effect_threshold: float | None = None,
    policy: CausalGuardrailsPolicy = DEFAULT_CAUSAL_GUARDRAILS_POLICY,
) -> CausalGuardrailDecision:
    """Turn evidence summary into deterministic constraints.

    Rules (simple + explainable):
    - If not enough data -> info.
    - If estimated effect is negative and CI is also fully negative -> warn/block.

    The caller chooses how to use constraints (DecisionCore merges them).
    """

    ev = dict(causal_evidence or {}) if isinstance(causal_evidence, dict) else {}
    n = int(ev.get("n_days") or ev.get("n") or 0)
    required_days = int(policy.min_n_days if min_n_days is None else min_n_days)

    if n < required_days:
        return CausalGuardrailDecision(
            ok=True,
            level="info",
            reason="insufficient_data",
            constraints={"causal_guardrail": {"status": policy.insufficient_data_status, "n_days": n}},
        )

    est = _as_float(ev.get("effect"))
    lo = _as_float(ev.get("ci_low"))
    hi = _as_float(ev.get("ci_high"))

    if est is None:
        return CausalGuardrailDecision(
            ok=True,
            level="info",
            reason="no_effect_estimate",
            constraints={"causal_guardrail": {"status": policy.no_estimate_status, "n_days": n}},
        )

    # Strong negative: CI below threshold
    thr = float(policy.negative_effect_threshold if negative_effect_threshold is None else negative_effect_threshold)
    if lo is not None and hi is not None:
        if hi < thr:
            return CausalGuardrailDecision(
                ok=False,
                level="block",
                reason="negative_effect_confident",
                constraints={
                    "mode": policy.safe_mode,
                    "reason": "causal_negative_effect",
                    "max_band": policy.low_band,
                    "causal_guardrail": {"status": policy.block_status, "effect": est, "ci": [lo, hi], "n_days": n},
                },
            )
        if est < thr and lo < thr:
            return CausalGuardrailDecision(
                ok=True,
                level="warn",
                reason="negative_effect_likely",
                constraints={
                    "mode": policy.cautious_mode,
                    "reason": "causal_negative_effect",
                    "causal_guardrail": {"status": policy.warn_status, "effect": est, "ci": [lo, hi], "n_days": n},
                },
            )

    # Mild negative without CI
    if est < thr:
        return CausalGuardrailDecision(
            ok=True,
            level="warn",
            reason="negative_effect",
            constraints={"mode": policy.cautious_mode, "reason": "causal_negative_effect", "causal_guardrail": {"status": policy.warn_status, "effect": est, "n_days": n}},
        )

    return CausalGuardrailDecision(
        ok=True,
        level="info",
        reason="ok",
        constraints={"causal_guardrail": {"status": policy.ok_status, "effect": est, "ci": [lo, hi] if lo is not None and hi is not None else None, "n_days": n}},
    )
