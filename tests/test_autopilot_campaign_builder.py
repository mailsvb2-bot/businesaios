from contracts.autopilot_contract import AutopilotConstraints, AutopilotContract
from core.growth.campaign_builder.budgeting import CampaignBudgetPolicy
from core.growth.campaign_builder.contracts import AutopilotCampaignBuildRequest
from core.growth.campaign_builder.service import AutopilotCampaignBuilder
from core.growth.campaign_builder.spec_codec import TrafficToAdsSpec
from core.traffic.ads_spec_builder import AdsSpecBuilder
from core.traffic.audience_selector import AudienceSelector
from core.traffic.bid_manager import BidManager
from core.traffic.budget_allocator import BudgetAllocator
from core.traffic.campaign_factory import CampaignFactory
from core.traffic.creative_generator import CreativeGenerator
from core.traffic.strategy_service import TrafficStrategyService


def _builder() -> AutopilotCampaignBuilder:
    traffic = TrafficStrategyService(
        campaign_factory=CampaignFactory(),
        audience_selector=AudienceSelector(),
        creative_generator=CreativeGenerator(),
        budget_allocator=BudgetAllocator(),
        bid_manager=BidManager(),
    )
    codec = TrafficToAdsSpec(builder=AdsSpecBuilder())
    return AutopilotCampaignBuilder(traffic=traffic, codec=codec, budget_policy=CampaignBudgetPolicy())


def test_campaign_builder_smoke_and_determinism():
    b = _builder()
    contract = AutopilotContract(
        contract_id="c1",
        tenant_id="t1",
        constraints=AutopilotConstraints(daily_budget_minor=10_00, currency="RUB"),
    )
    req = AutopilotCampaignBuildRequest(
        tenant_id="t1",
        platform="telegram_ads",
        account_id="acc1",
        what="Стоматология",
        offer_title="Осмотр + план лечения",
        region="Москва",
        total_budget_minor_7d=999_00,  # should clamp to 7 * 10.00 = 70.00
        budget_currency="RUB",
        target_cac_minor=500_00,
        destination={"type": "tg_inbox"},
        seed="seed1",
    )
    r1 = b.build(req=req, autopilot_contract=contract)
    r2 = b.build(req=req, autopilot_contract=contract)

    assert r1.ads_spec == r2.ads_spec
    assert r1.traffic_plan == r2.traffic_plan

    # clamp check
    daily_minor = r1.traffic_plan.campaign.budget.daily_budget_minor
    assert daily_minor == 10_00

    # command surface present
    assert r1.ads_spec["commands"][0]["action"] == "create_campaign"
    assert r1.ads_spec["commands"][0]["payload"]["name"]
