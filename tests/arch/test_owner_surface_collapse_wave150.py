from __future__ import annotations

import importlib
from pathlib import Path


PACKAGE_ALIAS_EXPECTATIONS = {
    'attribution': {
        'attribution_engine': 'AttributionEngine',
        'lead_to_revenue_resolver': 'LeadToRevenueResolver',
        'offline_conversion_mapper': 'OfflineConversionMapper',
    },
    'growth.seo': {
        'article_generator': 'ArticleGenerator',
        'content_refresh_planner': 'ContentRefreshPlanner',
        'internal_linking_planner': 'InternalLinkingPlanner',
        'keyword_clustering': 'KeywordClustering',
        'keyword_research': 'KeywordResearch',
        'local_intent_mapper': 'LocalIntentMapper',
        'location_page_generator': 'LocationPageGenerator',
        'meta_generator': 'MetaGenerator',
        'rank_tracking': 'RankTracking',
        'search_console_connector_adapter': 'SearchConsoleConnectorAdapter',
        'seo_performance_monitor': 'SeoPerformanceMonitor',
        'seo_strategy_builder': 'SeoStrategyBuilder',
        'service_page_generator': 'ServicePageGenerator',
    },
    'matching.scorers': {
        'capacity_fit_score': 'CapacityFitScore',
        'conversion_probability_score': 'ConversionProbabilityScore',
        'customer_satisfaction_probability_score': 'CustomerSatisfactionProbabilityScore',
        'fair_distribution_score': 'FairDistributionScore',
        'geo_fit_score': 'GeoFitScore',
        'intent_fit_score': 'IntentFitScore',
        'price_fit_score': 'PriceFitScore',
        'repeat_purchase_probability_score': 'RepeatPurchaseProbabilityScore',
        'reputation_fit_score': 'ReputationFitScore',
        'response_fit_score': 'ResponseFitScore',
        'revenue_potential_score': 'RevenuePotentialScore',
        'risk_penalty_score': 'RiskPenaltyScore',
    },
    'ml.scoring': {
        'audience_score_model': 'AudienceScoreModel',
        'channel_score_model': 'ChannelScoreModel',
        'creative_score_model': 'CreativeScoreModel',
        'lead_quality_model': 'LeadQualityModel',
        'platform_match_model': 'PlatformMatchModel',
        'revenue_potential_model': 'RevenuePotentialModel',
        'risk_score_model': 'RiskScoreModel',
        'seo_opportunity_model': 'SeoOpportunityModel',
    },
    'routing.policies': {
        'capacity_protection_policy': 'CapacityProtectionPolicy',
        'fair_rotation_policy': 'FairRotationPolicy',
        'fast_response_policy': 'FastResponsePolicy',
        'geo_locality_policy': 'GeoLocalityPolicy',
        'high_risk_request_policy': 'HighRiskRequestPolicy',
        'high_value_client_policy': 'HighValueClientPolicy',
        'new_business_ramp_policy': 'NewBusinessRampPolicy',
        'premium_supply_policy': 'PremiumSupplyPolicy',
        'reputation_safety_policy': 'ReputationSafetyPolicy',
        'routing_policy_registry': 'build_default_policies',
    },
}


OWNER_IMPORT_FILES = {
    'demand_seo/local_intent_page_builder.py': 'from growth.seo import LocalIntentMapper as GrowthLocalIntentMapper',
    'demand_seo/location_page_generator.py': 'from growth.seo import LocationPageGenerator as GrowthLocationPageGenerator',
    'demand_seo/rank_tracking.py': 'from growth.seo import RankTracking as GrowthRankTracking',
    'demand_seo/service_page_generator.py': 'from growth.seo import ServicePageGenerator as GrowthServicePageGenerator',
    'growth/core/growth_engine.py': 'from ml.scoring import RiskScoreModel, RevenuePotentialModel',
    'matching/ranking.py': 'from matching.scorers import (',
    'routing/router_policy_evaluator.py': 'from routing.policies import (',
}


def test_alias_modules_delegate_to_package_roots() -> None:
    for package_name, aliases in PACKAGE_ALIAS_EXPECTATIONS.items():
        package = importlib.import_module(package_name)
        for module_name, export_name in aliases.items():
            module = importlib.import_module(f'{package_name}.{module_name}')
            assert getattr(module, export_name) is getattr(package, export_name)
            assert module.__all__ == [export_name]
            assert module.__file__.replace('\\', '/').endswith(f'/{module_name}.py')


def test_internal_code_prefers_owner_surfaces_over_alias_submodules() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for relative_path, expected_import in OWNER_IMPORT_FILES.items():
        text = (repo_root / relative_path).read_text(encoding='utf-8')
        assert expected_import in text, relative_path
