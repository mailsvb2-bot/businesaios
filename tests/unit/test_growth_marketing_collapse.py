from growth import (
    ArticleGenerator,
    CampaignEngine,
    ContentRefreshPlanner,
    InquiryRouter,
    KeywordClustering,
    KeywordResearch,
    ListingContentBuilder,
    ListingOptimizer,
    PlatformOpportunityDetector,
    PlatformStrategyBuilder,
    RankImprovementPlanner,
    RankTracking,
    ReputationManager,
    ReviewRequestPlanner,
    SeoPerformanceMonitor,
    SeoStrategyBuilder,
)


def test_campaign_engine_assembles_seo_and_platform_packages() -> None:
    payload = {"channel": "google", "service": "therapy"}
    package = CampaignEngine().assemble_campaign(payload)
    assert package["seo"]["kind"] == "seo_engine_package"
    assert package["seo"]["seo_strategy"]["kind"] == "seo_strategy"
    assert package["seo"]["keyword_research"]["kind"] == "keyword_research"
    assert package["seo"]["rank_tracking"]["kind"] == "rank_tracking"
    assert package["platforms"]["kind"] == "platform_engine_package"
    assert package["platforms"]["platform_strategy"]["kind"] == "platform_strategy"
    assert package["platforms"]["listing_content"]["kind"] == "listing_content"
    assert package["platforms"]["review_requests"]["kind"] == "review_request_plan"


def test_legacy_seo_and_platform_imports_stay_compatible() -> None:
    payload = {"listing_id": "x", "page_id": "p-1"}
    assert SeoStrategyBuilder().build(payload)["kind"] == "seo_strategy"
    assert KeywordResearch().build(payload)["kind"] == "keyword_research"
    assert KeywordClustering().build(payload)["kind"] == "keyword_clusters"
    assert ArticleGenerator().build(payload)["kind"] == "article_spec"
    assert ContentRefreshPlanner().plan(payload)["kind"] == "refresh_plan"
    assert RankTracking().observe(payload)["kind"] == "rank_tracking"
    assert SeoPerformanceMonitor().observe(payload)["kind"] == "seo_performance"
    assert PlatformStrategyBuilder().build(payload)["kind"] == "platform_strategy"
    assert PlatformOpportunityDetector().detect(payload)["kind"] == "platform_opportunities"
    assert ListingContentBuilder().build(payload)["kind"] == "listing_content"
    assert ListingOptimizer().optimize(payload)["kind"] == "listing_optimization"
    assert RankImprovementPlanner().plan(payload)["kind"] == "rank_improvement_plan"
    assert ReputationManager().build(payload)["kind"] == "reputation_plan"
    assert ReviewRequestPlanner().plan(payload)["kind"] == "review_request_plan"
    assert InquiryRouter().route(payload)["kind"] == "inquiry_route"
