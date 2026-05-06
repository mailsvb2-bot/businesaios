from __future__ import annotations

from growth.campaign_engine import CampaignEngine

CANON_GROWTH_PLATFORMS_ALIAS_NAMESPACE = True

class InquiryRouter:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def route(self, payload: dict) -> dict:
        return self._engine.route_inquiries(payload)

class ListingContentBuilder:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_listing_content(payload)

class ListingOptimizer:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def optimize(self, payload: dict) -> dict:
        return self._engine.optimize_listing(payload)

class ListingTemplateRegistry:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def resolve(self, payload: dict) -> dict:
        return self._engine.resolve_listing_template(payload)

class PlatformOpportunityDetector:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def detect(self, payload: dict) -> dict:
        return self._engine.detect_platform_opportunities(payload)

class PlatformStrategyBuilder:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_platform_strategy(payload)

class RankImprovementPlanner:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_rank_improvement(payload)

class ReputationManager:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_reputation_plan(payload)

class ReviewRequestPlanner:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_review_requests(payload)

__all__ = [
    "CANON_GROWTH_PLATFORMS_ALIAS_NAMESPACE",
    "InquiryRouter",
    "ListingContentBuilder",
    "ListingOptimizer",
    "ListingTemplateRegistry",
    "PlatformOpportunityDetector",
    "PlatformStrategyBuilder",
    "RankImprovementPlanner",
    "ReputationManager",
    "ReviewRequestPlanner",
]
