from __future__ import annotations

from demand_product.first_revenue_detector import FirstRevenueDetector


def test_first_revenue_magic_moment():
    assert FirstRevenueDetector().detect({"first_revenue_seen": False, "revenue": 10.0}) is True


from demand_seo.location_page_generator import LocationPageGenerator


def test_demand_seo_location_page_generator_preserves_city_contract():
    page = LocationPageGenerator().build("amsterdam")
    assert page["city"] == "amsterdam"
    assert page["slug"] == "/amsterdam/"
    assert page["spec"]["kind"] == "location_page_spec"


from demand_seo.rank_tracking import RankTracking
from demand_seo.service_page_generator import ServicePageGenerator


def test_demand_seo_service_page_generator_preserves_category_contract():
    page = ServicePageGenerator().build("therapy")
    assert page["category"] == "therapy"
    assert page["slug"] == "/services/therapy/"
    assert page["spec"]["kind"] == "service_page_spec"


def test_demand_seo_rank_tracking_preserves_keyword_and_position_contract():
    record = RankTracking().record("therapy amsterdam", 3)
    assert record["keyword"] == "therapy amsterdam"
    assert record["position"] == 3
    assert record["observation"]["kind"] == "rank_tracking"


from demand_seo.local_intent_page_builder import LocalIntentPageBuilder


def test_demand_seo_local_intent_page_builder_preserves_slug_and_context_contract():
    page = LocalIntentPageBuilder().build("amsterdam", "therapy")
    assert page["city"] == "amsterdam"
    assert page["category"] == "therapy"
    assert page["slug"] == "/amsterdam/therapy/"
    assert page["intent_map"]["kind"] == "local_intent_map"
