from growth.core import GrowthEngine


def test_growth_engine_exposes_three_canonical_growth_packages() -> None:
    engine = GrowthEngine()
    payload = {"channel": "ads", "campaign_id": "c-1", "amount": 100.0}

    campaign = engine.assemble_campaign_package(payload)
    creative = engine.assemble_creative_package(payload)
    budget = engine.assemble_budget_package(payload)
    plan = engine.assemble_growth_plan(payload)

    assert campaign["kind"] == "campaign_engine_package"
    assert creative["kind"] == "creative_engine_package"
    assert budget["kind"] == "budget_engine_package"
    assert plan["campaign"] == campaign
    assert plan["creative"] == creative
    assert plan["budget"] == budget


def test_campaign_package_keeps_requested_campaign_scope() -> None:
    package = GrowthEngine().assemble_campaign_package({"channel": "meta_ads", "geo": "nl"})

    assert package["channels"]["kind"] == "channel_selection"
    assert package["audience"]["kind"] == "audience"
    assert package["campaign_structure"]["kind"] == "campaign"
    assert package["targeting"]["kind"] == "geo_targeting_plan"
