from growth import CampaignEngine, CreativeEngine, BudgetEngine
from growth.ads.audience_builder import AudienceBuilder
from growth.ads.budget_allocator import BudgetAllocator
from growth.ads.campaign_planner import CampaignPlanner
from growth.ads.channel_selector import ChannelSelector
from growth.ads.creative_variant_planner import CreativeVariantPlanner
from growth.ads.geo_targeting_planner import GeoTargetingPlanner
from growth.ads.keyword_campaign_builder import KeywordCampaignBuilder
from growth.ads.performance_monitor import PerformanceMonitor
from growth.ads.retargeting_planner import RetargetingPlanner
from growth.ads.scale_winner_detector import ScaleWinnerDetector
from growth.ads.underperforming_campaign_detector import UnderperformingCampaignDetector
from growth.landing.landing_ab_test_planner import LandingAbTestPlanner
from growth.landing.landing_publish_service import LandingPublishService


def test_growth_public_api_exports_new_engines():
    assert CampaignEngine.__name__ == 'CampaignEngine'
    assert CreativeEngine.__name__ == 'CreativeEngine'
    assert BudgetEngine.__name__ == 'BudgetEngine'


def test_campaign_engine_assembles_growth_package():
    payload = {'channel': 'meta_ads', 'geo': 'nl'}
    package = CampaignEngine().assemble_campaign(payload)
    assert package['kind'] == 'campaign_engine_package'
    assert package['channels']['kind'] == 'channel_selection'
    assert package['audience']['kind'] == 'audience'
    assert package['campaign_structure']['kind'] == 'campaign'
    assert package['targeting']['kind'] == 'geo_targeting_plan'
    assert package['retargeting']['kind'] == 'retargeting_plan'
    assert package['keyword_campaign']['kind'] == 'keyword_campaign'
    assert package['performance_snapshot']['kind'] == 'performance_snapshot'
    assert package['scale_candidates']['kind'] == 'scale_candidates'
    assert package['underperforming_campaigns']['kind'] == 'underperforming_campaigns'


def test_creative_engine_assembles_growth_package():
    payload = {'page_id': 'landing-1'}
    package = CreativeEngine().assemble_landing(payload)
    assert package['kind'] == 'creative_engine_package'
    assert package['creative_variants']['kind'] == 'creative_variants'
    assert package['landing_page']['kind'] == 'landing_page'
    assert package['ab_test']['kind'] == 'landing_ab_test'


def test_budget_engine_assembles_growth_package():
    payload = {'amount': 100.0}
    package = BudgetEngine().assemble_budget(payload)
    assert package['kind'] == 'budget_engine_package'
    assert package['budget_allocation']['kind'] == 'budget_allocation'
    assert package['bid_strategy']['kind'] == 'bid_strategy'


def test_legacy_growth_imports_stay_compatible():
    payload = {'campaign_id': 'c-1'}
    assert AudienceBuilder().build(payload)['kind'] == 'audience'
    assert BudgetAllocator().allocate(payload)['kind'] == 'budget_allocation'
    assert CampaignPlanner().plan(payload)['kind'] == 'campaign_plan'
    assert ChannelSelector().select(payload)['kind'] == 'channel_selection'
    assert CreativeVariantPlanner().plan(payload)['kind'] == 'creative_variants'
    assert GeoTargetingPlanner().plan(payload)['kind'] == 'geo_targeting_plan'
    assert KeywordCampaignBuilder().build(payload)['kind'] == 'keyword_campaign'
    assert PerformanceMonitor().observe(payload)['kind'] == 'performance_snapshot'
    assert RetargetingPlanner().plan(payload)['kind'] == 'retargeting_plan'
    assert ScaleWinnerDetector().detect(payload)['kind'] == 'scale_candidates'
    assert UnderperformingCampaignDetector().detect(payload)['kind'] == 'underperforming_campaigns'
    assert LandingAbTestPlanner().plan(payload)['kind'] == 'landing_ab_test'
    assert LandingPublishService().publish(payload)['kind'] == 'publish_request'
