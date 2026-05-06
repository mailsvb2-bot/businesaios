from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DecisionStatePricingPolicy:
    negative_expected_profit_floor: float = 0.0
    low_conversion_probability_threshold: float = 0.01
    high_price_sensitivity_threshold: float = -2.0
    low_band: str = "low"
    standard_band: str = "standard"
    safe_mode: str = "safe"
    negative_expected_profit_reason: str = "negative_expected_profit_at_current_price"
    low_conversion_reason: str = "very_low_conversion_probability"
    high_price_sensitivity_reason: str = "high_price_sensitivity"
    behavior_guardrail_reason: str = "behavior_guardrails_violation"
    disallowed_offer_prefixes: tuple[str, ...] = ("offer_90", "offer_bundle")


@dataclass(frozen=True)
class DecisionStateCausalPolicy:
    pricing_source: str = "pricing"
    pricing_min_n_days: int = 14
    negative_effect_threshold: float = 0.0


@dataclass(frozen=True)
class DecisionStateConstraintsPolicy:
    pricing: DecisionStatePricingPolicy = field(default_factory=DecisionStatePricingPolicy)
    causal: DecisionStateCausalPolicy = field(default_factory=DecisionStateCausalPolicy)


DEFAULT_DECISION_STATE_CONSTRAINTS_POLICY = DecisionStateConstraintsPolicy()
