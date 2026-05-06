from __future__ import annotations

from marketplace.demand_pipeline import DemandPipeline, process_demand
from marketplace.request_quote_flow import RequestQuoteFlow
from shared.kinded_payloads import build_kinded_payload


class BusinessCards:
    def render(self, profile: object) -> dict[str, object]:
        return {"business_id": profile.business_id, "name": profile.name, "tags": profile.tags}


class BusinessReputationIndex:
    def compute(self, payload: dict) -> dict:
        return build_kinded_payload("business_reputation_index", payload)


class ClientEntrypoints:
    def list_entrypoints(self) -> tuple[str, ...]:
        return ("search", "quote_request", "instant_match")


class ClientIntentRegistry:
    def register(self, payload: dict) -> dict:
        return build_kinded_payload("client_intent", payload)


class LeadExchange:
    def share(self, payload: dict) -> dict:
        return build_kinded_payload("lead_exchange", payload)


class LocationPages:
    def build_slug(self, city: str, category: str) -> str:
        return f"/{city.strip().lower()}/{category.strip().lower()}/"


class MarketplaceMetrics:
    def summarize(self, views: int, requests: int, conversions: int) -> dict[str, float]:
        return {
            "request_rate": requests / max(1, views),
            "conversion_rate": conversions / max(1, requests),
        }


class MarketplacePolicy:
    def evaluate(self, payload: dict) -> dict:
        return build_kinded_payload("marketplace_policy_result", payload)


class MarketplaceRanking:
    def rank(self, payload: dict) -> dict:
        return build_kinded_payload("marketplace_ranking", payload)


class NetworkGrowthMetrics:
    def observe(self, payload: dict) -> dict:
        return build_kinded_payload("network_growth_metrics", payload)


class RecommendationEngine:
    def recommend(self, payload: dict) -> dict:
        return build_kinded_payload("recommendations", payload)


class RecommendationFeed:
    def build(self, routed_candidates: tuple[object, ...]) -> list[dict[str, object]]:
        return [{"business_id": c.business_id, "score": c.rank_score} for c in routed_candidates]


class ReviewSurface:
    def render(self, review_score: float, review_count: int) -> dict[str, object]:
        return {"review_score": float(review_score), "review_count": int(review_count)}


class SearchResultsBuilder:
    def build(self, profiles: tuple[object, ...]) -> list[dict[str, object]]:
        return [{"business_id": p.business_id, "name": p.name} for p in profiles]


class ServiceCategoryTree:
    def categories(self) -> tuple[str, ...]:
        return ("general", "premium", "local")


__all__ = (
    "BusinessCards",
    "BusinessReputationIndex",
    "ClientEntrypoints",
    "ClientIntentRegistry",
    "DemandPipeline",
    "LeadExchange",
    "LocationPages",
    "MarketplaceMetrics",
    "MarketplacePolicy",
    "MarketplaceRanking",
    "NetworkGrowthMetrics",
    "RecommendationEngine",
    "RecommendationFeed",
    "RequestQuoteFlow",
    "ReviewSurface",
    "SearchResultsBuilder",
    "ServiceCategoryTree",
    "process_demand",
)
