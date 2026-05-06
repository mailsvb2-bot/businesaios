from growth.ads import BudgetAllocator, CampaignPlanner, KeywordCampaignBuilder, PerformanceMonitor
from growth.core import GrowthEngine
from growth.landing import LandingAbTestPlanner, LandingPublishService


def test_growth_engine_assembles_unified_growth_plan() -> None:
    payload = {'channel': 'ads', 'campaign_id': 'c-1', 'amount': 120.0}
    plan = GrowthEngine().assemble_growth_plan(payload)
    assert plan['kind'] == 'growth_plan'
    assert plan['objective_name']
    assert plan['campaign']['kind'] == 'campaign_engine_package'
    assert plan['creative']['kind'] == 'creative_engine_package'
    assert plan['budget']['kind'] == 'budget_engine_package'


def test_growth_package_exports_resolve_collapsed_wrappers() -> None:
    payload = {'campaign_id': 'c-1'}
    assert BudgetAllocator().allocate(payload)['kind'] == 'budget_allocation'
    assert CampaignPlanner().plan(payload)['kind'] == 'campaign_plan'
    assert KeywordCampaignBuilder().build(payload)['kind'] == 'keyword_campaign'
    assert PerformanceMonitor().observe(payload)['kind'] == 'performance_snapshot'
    assert LandingAbTestPlanner().plan(payload)['kind'] == 'landing_ab_test'
    assert LandingPublishService().publish(payload)['kind'] == 'publish_request'


def test_growth_engine_plan_includes_marketing_subpackages() -> None:
    plan = GrowthEngine().assemble_growth_plan({"channel": "organic"})
    assert plan["campaign"]["seo"]["kind"] == "seo_engine_package"
    assert plan["campaign"]["platforms"]["kind"] == "platform_engine_package"
