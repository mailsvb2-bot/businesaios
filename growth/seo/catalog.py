from growth.campaign_engine import CampaignEngine


class ArticleGenerator:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_article_spec(payload)


class ContentRefreshPlanner:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_content_refresh(payload)


class InternalLinkingPlanner:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def plan(self, payload: dict) -> dict:
        return self._engine.plan_internal_linking(payload)


class KeywordClustering:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_keyword_clusters(payload)


class KeywordResearch:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_keyword_research(payload)


class LocalIntentMapper:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def map(self, payload: dict) -> dict:
        return self._engine.map_local_intent(payload)


class LocationPageGenerator:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_location_page_spec(payload)


class MetaGenerator:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_meta_spec(payload)


class RankTracking:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def observe(self, payload: dict) -> dict:
        return self._engine.observe_rank_tracking(payload)


class SearchConsoleConnectorAdapter:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def adapt(self, payload: dict) -> dict:
        return self._engine.adapt_search_console(payload)


class SeoPerformanceMonitor:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def observe(self, payload: dict) -> dict:
        return self._engine.observe_seo_performance(payload)


class SeoStrategyBuilder:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_seo_strategy(payload)


class ServicePageGenerator:
    def __init__(self, *, engine: CampaignEngine | None = None) -> None:
        self._engine = engine or CampaignEngine()

    def build(self, payload: dict) -> dict:
        return self._engine.build_service_page_spec(payload)
