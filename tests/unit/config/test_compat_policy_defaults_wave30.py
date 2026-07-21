from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from config.ads_aggregates_policy import AdsAggregatesPolicy, DEFAULT_ADS_AGGREGATES_POLICY
from config.ads_policy_defaults import AdsAutopilotPolicyDefaults, DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS
from config.ads_rules_policy import AdsRulesPolicy, DEFAULT_ADS_RULES_POLICY
from config.budget_limits import BudgetLimits as CompatBudgetLimits
from config.business_defaults import BusinessDefaults as CompatBusinessDefaults
from config.business_quality_thresholds import (
    FRAUD_RISK_CEILING,
    NO_RESPONSE_RATE_CEILING,
    QUALITY_FLOOR,
    REPUTATION_FLOOR,
)
from config.cache_window_policy import CacheWindowPolicy, DEFAULT_CACHE_WINDOW_POLICY
from config.catalog import (
    FAIR_ROTATION_WEIGHT as CATALOG_FAIR_ROTATION_WEIGHT,
    FRAUD_RISK_CEILING as CATALOG_FRAUD_RISK_CEILING,
    HIGH_VALUE_PRIORITY_WEIGHT as CATALOG_HIGH_VALUE_PRIORITY_WEIGHT,
    NEW_SUPPLY_SUPPORT_BONUS as CATALOG_NEW_SUPPLY_SUPPORT_BONUS,
    NO_RESPONSE_RATE_CEILING as CATALOG_NO_RESPONSE_RATE_CEILING,
    PREMIUM_QUALITY_WEIGHT as CATALOG_PREMIUM_QUALITY_WEIGHT,
    QUALITY_FLOOR as CATALOG_QUALITY_FLOOR,
    REPUTATION_FLOOR as CATALOG_REPUTATION_FLOOR,
    STATE_FEED_ORDER as CATALOG_STATE_FEED_ORDER,
    BudgetLimits,
    BusinessDefaults,
    ExperimentLimits,
    NotificationDefaults,
    PlatformLimits,
    RiskThresholds,
)
from config.channel_defaults import ChannelDefaults
from config.economics_ltv_policy import DEFAULT_LTV_BUILDER_POLICY, LTVBuilderPolicy
from config.economics_spend_cap_policy import (
    DEFAULT_ECONOMICS_SPEND_CAP_POLICY_DEFAULTS,
    EconomicsSpendCapPolicyDefaults,
)
from config.experiment_limits import ExperimentLimits as CompatExperimentLimits
from config.fair_distribution_rules import FAIR_ROTATION_WEIGHT, NEW_SUPPLY_SUPPORT_BONUS
from config.feed_merge_rules import STATE_FEED_ORDER
from config.governance_review_policy import GovernanceReviewPolicy
from config.growth_autopilot_policy import DEFAULT_GROWTH_AUTOPILOT_POLICY, GrowthAutopilotPolicy
from config.high_value_client_rules import HIGH_VALUE_PRIORITY_WEIGHT, PREMIUM_QUALITY_WEIGHT
from config.llm_budget_policy import DEFAULT_LLM_BUDGET_POLICY, LLMBudgetPolicy
from config.llm_cache_policy import LLMCachePolicy
from config.marketing_llm_telemetry_policy import (
    DEFAULT_MARKETING_LLM_TELEMETRY_POLICY,
    MarketingLLMTelemetryPolicy,
)
from config.notification_defaults import NotificationDefaults as CompatNotificationDefaults
from config.platform_limits import PlatformLimits as CompatPlatformLimits
from config.risk_thresholds import RiskThresholds as CompatRiskThresholds
from config.rollout_guard_policy import RolloutGuardPolicy
from config.staged_rollout_policy import DEFAULT_STAGED_ROLLOUT_POLICY, StagedRolloutPolicy


def test_policy_singletons_match_explicit_default_instances() -> None:
    assert DEFAULT_ADS_AGGREGATES_POLICY == AdsAggregatesPolicy()
    assert DEFAULT_ADS_AUTOPILOT_POLICY_DEFAULTS == AdsAutopilotPolicyDefaults()
    assert DEFAULT_ADS_RULES_POLICY == AdsRulesPolicy()
    assert DEFAULT_CACHE_WINDOW_POLICY == CacheWindowPolicy()
    assert DEFAULT_LTV_BUILDER_POLICY == LTVBuilderPolicy()
    assert DEFAULT_ECONOMICS_SPEND_CAP_POLICY_DEFAULTS == EconomicsSpendCapPolicyDefaults()
    assert DEFAULT_GROWTH_AUTOPILOT_POLICY == GrowthAutopilotPolicy()
    assert DEFAULT_LLM_BUDGET_POLICY == LLMBudgetPolicy()
    assert DEFAULT_MARKETING_LLM_TELEMETRY_POLICY == MarketingLLMTelemetryPolicy()
    assert DEFAULT_STAGED_ROLLOUT_POLICY == StagedRolloutPolicy()


def test_policy_defaults_are_explicit_and_immutable() -> None:
    assert RolloutGuardPolicy().full_rollout_pct == 100
    assert ChannelDefaults().platforms == "enabled"
    assert LLMCachePolicy().max_items == 2048
    assert GovernanceReviewPolicy().risk_review_threshold == 0.70

    with pytest.raises(FrozenInstanceError):
        DEFAULT_LLM_BUDGET_POLICY.user_tokens_per_day = 1  # type: ignore[misc]


def test_compatibility_wrappers_preserve_canonical_identity_and_values() -> None:
    assert CompatBudgetLimits is BudgetLimits
    assert CompatBusinessDefaults is BusinessDefaults
    assert CompatExperimentLimits is ExperimentLimits
    assert CompatNotificationDefaults is NotificationDefaults
    assert CompatPlatformLimits is PlatformLimits
    assert CompatRiskThresholds is RiskThresholds

    assert QUALITY_FLOOR == CATALOG_QUALITY_FLOOR
    assert REPUTATION_FLOOR == CATALOG_REPUTATION_FLOOR
    assert NO_RESPONSE_RATE_CEILING == CATALOG_NO_RESPONSE_RATE_CEILING
    assert FRAUD_RISK_CEILING == CATALOG_FRAUD_RISK_CEILING
    assert FAIR_ROTATION_WEIGHT == CATALOG_FAIR_ROTATION_WEIGHT
    assert NEW_SUPPLY_SUPPORT_BONUS == CATALOG_NEW_SUPPLY_SUPPORT_BONUS
    assert HIGH_VALUE_PRIORITY_WEIGHT == CATALOG_HIGH_VALUE_PRIORITY_WEIGHT
    assert PREMIUM_QUALITY_WEIGHT == CATALOG_PREMIUM_QUALITY_WEIGHT
    assert STATE_FEED_ORDER is CATALOG_STATE_FEED_ORDER
