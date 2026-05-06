from __future__ import annotations

import importlib
import sys
from typing import Any

CANON_GROWTH_ADS_ALIAS_NAMESPACE = True

_ALIAS_MAP = {
    "audience_builder": "growth.campaign_engine",
    "bid_strategy_selector": "growth.budget_engine",
    "budget_allocator": "growth.budget_engine",
    "campaign_factory": "growth.campaign_engine",
    "campaign_planner": "growth.campaign_engine",
    "campaign_template_registry": "growth.campaign_engine",
    "channel_selector": "growth.campaign_engine",
    "creative_brief_builder": "growth.creative_engine",
    "creative_variant_planner": "growth.creative_engine",
    "geo_targeting_planner": "growth.campaign_engine",
    "keyword_campaign_builder": "growth.campaign_engine",
    "performance_monitor": "growth.campaign_engine",
    "retargeting_planner": "growth.campaign_engine",
    "scale_winner_detector": "growth.campaign_engine",
    "underperforming_campaign_detector": "growth.campaign_engine",
}

_PUBLIC_ATTRS = {
    "AudienceBuilder": ("growth.campaign_engine", "AudienceBuilder"),
    "BidStrategySelector": ("growth.budget_engine", "BidStrategySelector"),
    "BudgetAllocator": ("growth.budget_engine", "BudgetAllocator"),
    "CampaignFactory": ("growth.campaign_engine", "CampaignFactory"),
    "CampaignPlanner": ("growth.campaign_engine", "CampaignPlanner"),
    "CampaignTemplateRegistry": ("growth.campaign_engine", "CampaignTemplateRegistry"),
    "ChannelSelector": ("growth.campaign_engine", "ChannelSelector"),
    "CreativeBriefBuilder": ("growth.creative_engine", "CreativeBriefBuilder"),
    "CreativeVariantPlanner": ("growth.creative_engine", "CreativeVariantPlanner"),
    "GeoTargetingPlanner": ("growth.campaign_engine", "GeoTargetingPlanner"),
    "KeywordCampaignBuilder": ("growth.campaign_engine", "KeywordCampaignBuilder"),
    "PerformanceMonitor": ("growth.campaign_engine", "PerformanceMonitor"),
    "RetargetingPlanner": ("growth.campaign_engine", "RetargetingPlanner"),
    "ScaleWinnerDetector": ("growth.campaign_engine", "ScaleWinnerDetector"),
    "UnderperformingCampaignDetector": ("growth.campaign_engine", "UnderperformingCampaignDetector"),
}


def _install_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target in _ALIAS_MAP.items():
        module = importlib.import_module(target)
        sys.modules[f"{__name__}.{alias_name}"] = module
        setattr(package, alias_name, module)


_install_aliases()


def __getattr__(name: str) -> Any:
    target = _PUBLIC_ATTRS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = ["CANON_GROWTH_ADS_ALIAS_NAMESPACE", *sorted(_PUBLIC_ATTRS)]
