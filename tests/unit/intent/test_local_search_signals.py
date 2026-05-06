from intent.local_search.geo_radius_builder import GeoRadiusBuilder
from intent.local_search.local_intent_mapper import LocalIntentMapper
from intent.local_search.local_service_query_parser import LocalServiceQueryParser
from intent.local_search.near_me_detector import NearMeDetector
from intent.local_search.service_area_match_prep import ServiceAreaMatchPrep


def test_local_search_primitives_share_consistent_signals() -> None:
    text = "Therapy near me"
    assert NearMeDetector()(text) is True
    assert LocalIntentMapper()(text) == "local"
    assert GeoRadiusBuilder()(text) == 5
    parsed = LocalServiceQueryParser()(text)
    assert parsed["query"] == "therapy near me"
    assert parsed["tokens"] == ("therapy", "near", "me")
    prepared = ServiceAreaMatchPrep()(text)
    assert prepared["service_area_ready"] is True
    assert prepared["text"] == "therapy near me"
