from __future__ import annotations

from growth.engine_base import GrowthEngineSurface
from growth.engine_contract import (
    CAMPAIGN_ENGINE_PACKAGE_KIND,
    PLATFORM_ENGINE_PACKAGE_KIND,
    SEO_ENGINE_PACKAGE_KIND,
    build_package,
)


class CampaignEngine(GrowthEngineSurface):

    def build_audience(self, payload: dict | None) -> dict:
        return self.artifact("audience", payload)

    def select_channel(self, payload: dict | None) -> dict:
        return self.artifact("channel_selection", payload)

    def build_campaign_structure(self, payload: dict | None) -> dict:
        return self.artifact("campaign", payload)

    def resolve_campaign_template(self, payload: dict | None) -> dict:
        return self.artifact("campaign_template", payload)

    def plan_targeting(self, payload: dict | None) -> dict:
        return self.artifact("geo_targeting_plan", payload)

    def plan_retargeting(self, payload: dict | None) -> dict:
        return self.artifact("retargeting_plan", payload)

    def plan_campaign(self, payload: dict | None) -> dict:
        return self.artifact("campaign_plan", payload)

    def build_keyword_campaign(self, payload: dict | None) -> dict:
        return self.artifact("keyword_campaign", payload)

    def observe_performance(self, payload: dict | None) -> dict:
        return self.artifact("performance_snapshot", payload)

    def detect_scale_candidates(self, payload: dict | None) -> dict:
        return self.artifact("scale_candidates", payload)

    def detect_underperforming_campaigns(self, payload: dict | None) -> dict:
        return self.artifact("underperforming_campaigns", payload)

    def build_seo_strategy(self, payload: dict | None) -> dict:
        return self.artifact("seo_strategy", payload)

    def build_keyword_research(self, payload: dict | None) -> dict:
        return self.artifact("keyword_research", payload)

    def build_keyword_clusters(self, payload: dict | None) -> dict:
        return self.artifact("keyword_clusters", payload)

    def map_local_intent(self, payload: dict | None) -> dict:
        return self.artifact("local_intent_map", payload)

    def build_article_spec(self, payload: dict | None) -> dict:
        return self.artifact("article_spec", payload)

    def build_service_page_spec(self, payload: dict | None) -> dict:
        return self.artifact("service_page_spec", payload)

    def build_location_page_spec(self, payload: dict | None) -> dict:
        return self.artifact("location_page_spec", payload)

    def build_meta_spec(self, payload: dict | None) -> dict:
        return self.artifact("meta_spec", payload)

    def plan_internal_linking(self, payload: dict | None) -> dict:
        return self.artifact("linking_plan", payload)

    def plan_content_refresh(self, payload: dict | None) -> dict:
        return self.artifact("refresh_plan", payload)

    def adapt_search_console(self, payload: dict | None) -> dict:
        return self.artifact("search_console_payload", payload)

    def observe_rank_tracking(self, payload: dict | None) -> dict:
        return self.artifact("rank_tracking", payload)

    def observe_seo_performance(self, payload: dict | None) -> dict:
        return self.artifact("seo_performance", payload)

    def build_platform_strategy(self, payload: dict | None) -> dict:
        return self.artifact("platform_strategy", payload)

    def detect_platform_opportunities(self, payload: dict | None) -> dict:
        return self.artifact("platform_opportunities", payload)

    def build_listing_content(self, payload: dict | None) -> dict:
        return self.artifact("listing_content", payload)

    def resolve_listing_template(self, payload: dict | None) -> dict:
        return self.artifact("listing_template", payload)

    def optimize_listing(self, payload: dict | None) -> dict:
        return self.artifact("listing_optimization", payload)

    def plan_rank_improvement(self, payload: dict | None) -> dict:
        return self.artifact("rank_improvement_plan", payload)

    def build_reputation_plan(self, payload: dict | None) -> dict:
        return self.artifact("reputation_plan", payload)

    def plan_review_requests(self, payload: dict | None) -> dict:
        return self.artifact("review_request_plan", payload)

    def route_inquiries(self, payload: dict | None) -> dict:
        return self.artifact("inquiry_route", payload)

    def assemble_seo(self, payload: dict | None) -> dict:
        normalized = self.payload(payload)
        return build_package(
            SEO_ENGINE_PACKAGE_KIND,
            normalized,
            seo_strategy=self.build_seo_strategy(normalized),
            keyword_research=self.build_keyword_research(normalized),
            keyword_clusters=self.build_keyword_clusters(normalized),
            local_intent=self.map_local_intent(normalized),
            article_spec=self.build_article_spec(normalized),
            service_page=self.build_service_page_spec(normalized),
            location_page=self.build_location_page_spec(normalized),
            meta_spec=self.build_meta_spec(normalized),
            internal_linking=self.plan_internal_linking(normalized),
            content_refresh=self.plan_content_refresh(normalized),
            search_console=self.adapt_search_console(normalized),
            rank_tracking=self.observe_rank_tracking(normalized),
            seo_performance=self.observe_seo_performance(normalized),
        )

    def assemble_platforms(self, payload: dict | None) -> dict:
        normalized = self.payload(payload)
        return build_package(
            PLATFORM_ENGINE_PACKAGE_KIND,
            normalized,
            platform_strategy=self.build_platform_strategy(normalized),
            platform_opportunities=self.detect_platform_opportunities(normalized),
            listing_content=self.build_listing_content(normalized),
            listing_template=self.resolve_listing_template(normalized),
            listing_optimization=self.optimize_listing(normalized),
            rank_improvement=self.plan_rank_improvement(normalized),
            reputation=self.build_reputation_plan(normalized),
            review_requests=self.plan_review_requests(normalized),
            inquiry_route=self.route_inquiries(normalized),
        )

    def assemble_campaign(self, payload: dict | None) -> dict:
        normalized = self.payload(payload)
        return build_package(
            CAMPAIGN_ENGINE_PACKAGE_KIND,
            normalized,
            channels=self.select_channel(normalized),
            audience=self.build_audience(normalized),
            campaign_structure=self.build_campaign_structure(normalized),
            targeting=self.plan_targeting(normalized),
            retargeting=self.plan_retargeting(normalized),
            keyword_campaign=self.build_keyword_campaign(normalized),
            performance_snapshot=self.observe_performance(normalized),
            scale_candidates=self.detect_scale_candidates(normalized),
            underperforming_campaigns=self.detect_underperforming_campaigns(normalized),
            seo=self.assemble_seo(normalized),
            platforms=self.assemble_platforms(normalized),
        )


class AudienceBuilder:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_audience(payload)


class ChannelSelector:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def select(self, payload: dict) -> dict:
        return self._engine.select_channel(payload)


class CampaignFactory:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_campaign_structure(payload)


class CampaignPlanner:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_campaign(payload)


class CampaignTemplateRegistry:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def resolve(self, payload: dict) -> dict:
        return self._engine.resolve_campaign_template(payload)




class KeywordCampaignBuilder:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_keyword_campaign(payload)


class PerformanceMonitor:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def observe(self, payload: dict) -> dict:
        return self._engine.observe_performance(payload)


class ScaleWinnerDetector:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def detect(self, payload: dict) -> dict:
        return self._engine.detect_scale_candidates(payload)


class UnderperformingCampaignDetector:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def detect(self, payload: dict) -> dict:
        return self._engine.detect_underperforming_campaigns(payload)


class GeoTargetingPlanner:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_targeting(payload)


class RetargetingPlanner:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_retargeting(payload)


__all__ = [
    "AudienceBuilder",
    "CampaignEngine",
    "CampaignFactory",
    "CampaignPlanner",
    "CampaignTemplateRegistry",
    "ChannelSelector",
    "GeoTargetingPlanner",
    "KeywordCampaignBuilder",
    "PerformanceMonitor",
    "RetargetingPlanner",
    "ScaleWinnerDetector",
    "UnderperformingCampaignDetector",
]
