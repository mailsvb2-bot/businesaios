from __future__ import annotations

from dataclasses import dataclass, field

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class AdsRLRewardPolicy:
    zero_reward: float = 0.0
    roas_when_no_spend_with_revenue: float = 10.0
    reward_mode_profit: str = 'profit'
    reward_mode_roas: str = 'roas'
    reward_mode_cpa: str = 'cpa'
    reward_mode_cpl: str = 'cpl'
    reward_mode_profit_fallback: str = 'profit_fallback'


@dataclass(frozen=True)
class AdsRLOptSpecPolicy:
    default_platform: str = 'unknown'
    default_reward_mode: str = 'profit'
    default_revenue_per_purchase: float = 0.0
    default_value_per_lead: float = 0.0
    default_canary: bool = True
    default_rollout_pct: float = 5.0
    min_rollout_pct: float = 0.0
    max_rollout_pct: float = 100.0
    default_min_history_steps: int = 30
    max_history_steps: int = 1_000_000
    default_max_budget_increase_pct: float = 10.0
    max_budget_increase_pct_limit: float = 500.0
    default_window_hours: int = 24
    max_window_hours: int = 24 * 28


@dataclass(frozen=True)
class AdsRLSafetyPolicy:
    rollout_bucket_modulus: int = 10_000
    rollout_bucket_divisor: float = 100.0
    rollout_pct_floor: float = 0.0
    rollout_pct_ceiling: float = 100.0
    percent_multiplier: float = 100.0
    non_positive_budget_floor: float = 0.0


@dataclass(frozen=True)
class AdsRLServicePolicy:
    arm_stats_limit: int = 2000
    default_propensity_denominator_floor: int = 1
    propensity_numerator: float = 1.0
    default_report_limit: int = 200
    reward_policy: AdsRLRewardPolicy = field(default_factory=AdsRLRewardPolicy)
    safety_policy: AdsRLSafetyPolicy = field(default_factory=AdsRLSafetyPolicy)


DEFAULT_ADS_RL_REWARD_POLICY = AdsRLRewardPolicy()
DEFAULT_ADS_RL_OPT_SPEC_POLICY = AdsRLOptSpecPolicy()
DEFAULT_ADS_RL_SAFETY_POLICY = AdsRLSafetyPolicy()
DEFAULT_ADS_RL_SERVICE_POLICY = AdsRLServicePolicy()
