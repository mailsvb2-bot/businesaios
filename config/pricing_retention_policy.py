from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class PricingOffPolicyDefaults:
    zero_reward_minor: float = 0.0
    zero_effective_n: float = 0.0
    zero_propensity: float = 0.0
    inverse_propensity_numerator: float = 1.0


@dataclass(frozen=True)
class RLPricingDefaults:
    grid_radius_pct: float = 0.20
    prior_alpha: float = 1.0
    prior_beta: float = 19.0
    temperature: float = 1.0
    epsilon: float = 0.05


@dataclass(frozen=True)
class PricingStopLossPolicy:
    unit_ratio: float = 1.0


@dataclass(frozen=True)
class RetentionEnginePolicy:
    decision_score_floor: float = 0.0
    sandbox_hazard: float = 0.0
    sandbox_readiness: float = 0.0
    outbound_queue_size_threshold: int = 500
    outbound_wait_p90_threshold_ms: float = 800.0
    daily_offer_cap_default: int = 2
    shown_events_scan_limit: int = 200
    shown_event_window_ms: int = 24 * 3600 * 1000
    score_complement_base: float = 1.0


DEFAULT_PRICING_OFF_POLICY_DEFAULTS = PricingOffPolicyDefaults()
DEFAULT_RL_PRICING_DEFAULTS = RLPricingDefaults()
DEFAULT_PRICING_STOP_LOSS_POLICY = PricingStopLossPolicy()
DEFAULT_RETENTION_ENGINE_POLICY = RetentionEnginePolicy()
