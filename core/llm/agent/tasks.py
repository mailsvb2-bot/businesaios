from __future__ import annotations

from enum import Enum


class TaskType(str, Enum):
    ADS_CREATIVE_GENERATE = "ads.creative.generate"
    ADS_CREATIVE_CRITIQUE = "ads.creative.critique"
    ADS_PLAN_BUILD = "ads.plan.build"
    ADS_ANALYTICS_SUMMARY = "ads.analytics.summary"

    OFFER_GENERATE = "offer.generate"
    OFFER_RISK_REDUCE = "offer.risk_reduce"
    PRICING_SUGGEST = "pricing.suggest"

    LANDING_COPY_GENERATE = "landing.copy.generate"
    LANDING_COPY_IMPROVE = "landing.copy.improve"
