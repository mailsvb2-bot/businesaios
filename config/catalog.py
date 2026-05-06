from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetLimits:
    daily_change_cap: object = 0.2
    max_campaign_budget: object = 2000.0
    max_total_daily_budget: object = 5000.0


@dataclass(frozen=True)
class BusinessDefaults:
    default_currency: object = 'EUR'
    default_region: object = 'NL'
    goal: object = 'profitable_growth'


QUALITY_FLOOR = 0.45
REPUTATION_FLOOR = 0.40
NO_RESPONSE_RATE_CEILING = 0.35
FRAUD_RISK_CEILING = 0.70


@dataclass(frozen=True)
class GravityWeights:
    base_demand_pressure: float = 0.50
    urgency_bonus: float = 0.20
    high_value_bonus: float = 0.15
    trust_bonus: float = 0.05
    base_supply_pressure: float = 0.45
    queue_weight: float = 0.35
    capacity_weight: float = 0.22
    response_weight: float = 0.08
    risk_weight: float = 0.20
    quality_weight: float = 0.30
    attraction_response_weight: float = 0.15
    margin_weight: float = 0.10
    feature_geo_weight: float = 0.10
    feature_time_weight: float = 0.05
    attraction_demand_weight: float = 0.30
    attraction_supply_penalty: float = 0.20
    missing_location_penalty: float = 0.05
    geo_mismatch_penalty: float = 0.35


@dataclass(frozen=True)
class MatchAdjustments:
    demand_pressure_weight: float = 0.25
    supply_pressure_penalty_weight: float = 0.20
    max_policy_adjustment_abs: float = 0.30


@dataclass(frozen=True)
class RoutingPolicyDeltas:
    high_value_premium_bonus: float = 0.12
    geo_local_bonus: float = 0.08
    geo_mismatch_penalty: float = 0.10
    fast_response_bonus: float = 0.08
    low_capacity_penalty: float = 0.25
    premium_quality_bonus: float = 0.10
    fair_rotation_bonus: float = 0.06
    new_business_bonus: float = 0.05
    low_reputation_penalty: float = 0.40
    high_risk_penalty: float = 0.50
    low_capacity_threshold: float = 0.15
    fast_response_threshold: float = 0.70
    low_reputation_threshold: float = 0.40
    high_risk_threshold: float = 0.70


GRAVITY_WEIGHTS = GravityWeights()
MATCH_ADJUSTMENTS = MatchAdjustments()
ROUTING_POLICY_DELTAS = RoutingPolicyDeltas()

INTENT_CONFIDENCE_FLOOR = 0.45
HIGH_VALUE_REVENUE_THRESHOLD = 500.0
DEDUP_WINDOW_MINUTES = 60
MATCH_BLOCK_RISK_THRESHOLD = 0.95
HIGH_RISK_BUSINESS_THRESHOLD = 0.70
NO_RESPONSE_RATE_LIMIT = 0.35
MAX_LOAD_RATIO = 0.95
MONOPOLY_LIMIT = 0.45
BAD_OUTCOME_ROLLBACK_THRESHOLD = 0.50


@dataclass(frozen=True)
class ExperimentLimits:
    max_parallel_experiments: object = 5
    min_runtime_days: object = 7
    max_budget_share: object = 0.25


FAIR_ROTATION_WEIGHT = 0.08
NEW_SUPPLY_SUPPORT_BONUS = 0.06

STATE_FEED_ORDER = (
    'crm',
    'calendar',
    'revenue',
    'lead_pipeline',
    'review',
    'response_time',
    'refund',
    'ad_performance',
)

HIGH_VALUE_PRIORITY_WEIGHT = 0.12
PREMIUM_QUALITY_WEIGHT = 0.10

MIN_REPLAY_SAMPLE_SIZE = 10
POLICY_PROMOTION_MIN_CONVERSION_RATE = 0.40
POLICY_ROLLBACK_MAX_CONVERSION_RATE = 0.20
POLICY_ROLLBACK_MIN_BAD_OUTCOME_RATE = 0.50
POLICY_MAX_ABSOLUTE_ADJUSTMENT = 0.30
POLICY_MIN_OUTCOME_ROWS_FOR_UPDATE = 5
POLICY_MIN_PER_BUSINESS_ROWS = 3
POLICY_CHANGE_EPSILON = 0.005
CAUSAL_RECENCY_WEIGHT = 0.70

MAX_CONCENTRATION_RATIO = 0.45
UTILIZATION_WARN_RATIO = 0.85
OVERFLOW_WARN_RATIO = 0.20


@dataclass(frozen=True)
class NotificationDefaults:
    email_enabled: object = True
    sms_enabled: object = False
    digest_hour: object = 9


@dataclass(frozen=True)
class PlatformLimits:
    max_replies_per_day: object = 100
    max_listing_updates_per_day: object = 20
    max_review_requests_per_day: object = 50


@dataclass(frozen=True)
class RiskThresholds:
    max_risk_score: object = 0.75
    min_confidence: object = 0.6
    manual_review_risk: object = 0.6


MAX_ROUTING_CANDIDATES = 10
MAX_RUNNER_UPS = 3
ROUTING_SCORE_FLOOR = 0.15
MAX_RETRY_ATTEMPTS = 3
MANUAL_REVIEW_REASON = "no_safe_candidates"

CONFIG_COMPAT_EXPORTS = {
    'budget_limits': {'BudgetLimits': 'config.catalog:BudgetLimits'},
    'business_defaults': {'BusinessDefaults': 'config.catalog:BusinessDefaults'},
    'business_quality_thresholds': {
        'QUALITY_FLOOR': 'config.catalog:QUALITY_FLOOR',
        'REPUTATION_FLOOR': 'config.catalog:REPUTATION_FLOOR',
        'NO_RESPONSE_RATE_CEILING': 'config.catalog:NO_RESPONSE_RATE_CEILING',
        'FRAUD_RISK_CEILING': 'config.catalog:FRAUD_RISK_CEILING',
    },
    'demand_scoring': {
        'GravityWeights': 'config.catalog:GravityWeights',
        'MatchAdjustments': 'config.catalog:MatchAdjustments',
        'RoutingPolicyDeltas': 'config.catalog:RoutingPolicyDeltas',
        'GRAVITY_WEIGHTS': 'config.catalog:GRAVITY_WEIGHTS',
        'MATCH_ADJUSTMENTS': 'config.catalog:MATCH_ADJUSTMENTS',
        'ROUTING_POLICY_DELTAS': 'config.catalog:ROUTING_POLICY_DELTAS',
    },
    'demand_thresholds': {
        'INTENT_CONFIDENCE_FLOOR': 'config.catalog:INTENT_CONFIDENCE_FLOOR',
        'HIGH_VALUE_REVENUE_THRESHOLD': 'config.catalog:HIGH_VALUE_REVENUE_THRESHOLD',
        'DEDUP_WINDOW_MINUTES': 'config.catalog:DEDUP_WINDOW_MINUTES',
        'MATCH_BLOCK_RISK_THRESHOLD': 'config.catalog:MATCH_BLOCK_RISK_THRESHOLD',
        'HIGH_RISK_BUSINESS_THRESHOLD': 'config.catalog:HIGH_RISK_BUSINESS_THRESHOLD',
        'NO_RESPONSE_RATE_LIMIT': 'config.catalog:NO_RESPONSE_RATE_LIMIT',
        'REPUTATION_FLOOR': 'config.catalog:REPUTATION_FLOOR',
        'MAX_LOAD_RATIO': 'config.catalog:MAX_LOAD_RATIO',
        'MONOPOLY_LIMIT': 'config.catalog:MONOPOLY_LIMIT',
        'BAD_OUTCOME_ROLLBACK_THRESHOLD': 'config.catalog:BAD_OUTCOME_ROLLBACK_THRESHOLD',
    },
    'experiment_limits': {'ExperimentLimits': 'config.catalog:ExperimentLimits'},
    'fair_distribution_rules': {
        'FAIR_ROTATION_WEIGHT': 'config.catalog:FAIR_ROTATION_WEIGHT',
        'NEW_SUPPLY_SUPPORT_BONUS': 'config.catalog:NEW_SUPPLY_SUPPORT_BONUS',
    },
    'feed_merge_rules': {'STATE_FEED_ORDER': 'config.catalog:STATE_FEED_ORDER'},
    'high_value_client_rules': {
        'HIGH_VALUE_PRIORITY_WEIGHT': 'config.catalog:HIGH_VALUE_PRIORITY_WEIGHT',
        'PREMIUM_QUALITY_WEIGHT': 'config.catalog:PREMIUM_QUALITY_WEIGHT',
    },
    'learning_thresholds': {
        'MIN_REPLAY_SAMPLE_SIZE': 'config.catalog:MIN_REPLAY_SAMPLE_SIZE',
        'POLICY_PROMOTION_MIN_CONVERSION_RATE': 'config.catalog:POLICY_PROMOTION_MIN_CONVERSION_RATE',
        'POLICY_ROLLBACK_MAX_CONVERSION_RATE': 'config.catalog:POLICY_ROLLBACK_MAX_CONVERSION_RATE',
        'POLICY_ROLLBACK_MIN_BAD_OUTCOME_RATE': 'config.catalog:POLICY_ROLLBACK_MIN_BAD_OUTCOME_RATE',
        'POLICY_MAX_ABSOLUTE_ADJUSTMENT': 'config.catalog:POLICY_MAX_ABSOLUTE_ADJUSTMENT',
        'POLICY_MIN_OUTCOME_ROWS_FOR_UPDATE': 'config.catalog:POLICY_MIN_OUTCOME_ROWS_FOR_UPDATE',
        'POLICY_MIN_PER_BUSINESS_ROWS': 'config.catalog:POLICY_MIN_PER_BUSINESS_ROWS',
        'POLICY_CHANGE_EPSILON': 'config.catalog:POLICY_CHANGE_EPSILON',
        'CAUSAL_RECENCY_WEIGHT': 'config.catalog:CAUSAL_RECENCY_WEIGHT',
    },
    'market_balance_limits': {
        'MAX_CONCENTRATION_RATIO': 'config.catalog:MAX_CONCENTRATION_RATIO',
        'UTILIZATION_WARN_RATIO': 'config.catalog:UTILIZATION_WARN_RATIO',
        'OVERFLOW_WARN_RATIO': 'config.catalog:OVERFLOW_WARN_RATIO',
    },
    'notification_defaults': {'NotificationDefaults': 'config.catalog:NotificationDefaults'},
    'platform_limits': {'PlatformLimits': 'config.catalog:PlatformLimits'},
    'risk_thresholds': {'RiskThresholds': 'config.catalog:RiskThresholds'},
    'routing_limits': {
        'MAX_ROUTING_CANDIDATES': 'config.catalog:MAX_ROUTING_CANDIDATES',
        'MAX_RUNNER_UPS': 'config.catalog:MAX_RUNNER_UPS',
        'ROUTING_SCORE_FLOOR': 'config.catalog:ROUTING_SCORE_FLOOR',
        'MAX_RETRY_ATTEMPTS': 'config.catalog:MAX_RETRY_ATTEMPTS',
        'MANUAL_REVIEW_REASON': 'config.catalog:MANUAL_REVIEW_REASON',
    },
}

__all__ = (
    'CONFIG_COMPAT_EXPORTS',
    'BudgetLimits', 'BusinessDefaults', 'QUALITY_FLOOR', 'REPUTATION_FLOOR',
    'NO_RESPONSE_RATE_CEILING', 'FRAUD_RISK_CEILING', 'GravityWeights',
    'MatchAdjustments', 'RoutingPolicyDeltas', 'GRAVITY_WEIGHTS',
    'MATCH_ADJUSTMENTS', 'ROUTING_POLICY_DELTAS', 'INTENT_CONFIDENCE_FLOOR',
    'HIGH_VALUE_REVENUE_THRESHOLD', 'DEDUP_WINDOW_MINUTES',
    'MATCH_BLOCK_RISK_THRESHOLD', 'HIGH_RISK_BUSINESS_THRESHOLD',
    'NO_RESPONSE_RATE_LIMIT', 'MAX_LOAD_RATIO', 'MONOPOLY_LIMIT',
    'BAD_OUTCOME_ROLLBACK_THRESHOLD', 'ExperimentLimits',
    'FAIR_ROTATION_WEIGHT', 'NEW_SUPPLY_SUPPORT_BONUS', 'STATE_FEED_ORDER',
    'HIGH_VALUE_PRIORITY_WEIGHT', 'PREMIUM_QUALITY_WEIGHT',
    'MIN_REPLAY_SAMPLE_SIZE', 'POLICY_PROMOTION_MIN_CONVERSION_RATE',
    'POLICY_ROLLBACK_MAX_CONVERSION_RATE', 'POLICY_ROLLBACK_MIN_BAD_OUTCOME_RATE',
    'POLICY_MAX_ABSOLUTE_ADJUSTMENT', 'POLICY_MIN_OUTCOME_ROWS_FOR_UPDATE',
    'POLICY_MIN_PER_BUSINESS_ROWS', 'POLICY_CHANGE_EPSILON',
    'CAUSAL_RECENCY_WEIGHT', 'MAX_CONCENTRATION_RATIO', 'UTILIZATION_WARN_RATIO',
    'OVERFLOW_WARN_RATIO', 'NotificationDefaults', 'PlatformLimits',
    'RiskThresholds', 'MAX_ROUTING_CANDIDATES', 'MAX_RUNNER_UPS',
    'ROUTING_SCORE_FLOOR', 'MAX_RETRY_ATTEMPTS', 'MANUAL_REVIEW_REASON',
)
