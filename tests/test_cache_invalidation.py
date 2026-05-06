from __future__ import annotations
from observability.platform.telemetry.event_store import InMemoryEventStore
from core.growth.ads_reco_cache import AdsRecommendationCache

def test_cache_fp_invalidation():
    es = InMemoryEventStore()
    cache = AdsRecommendationCache(store=es, ttl_minutes=120, scan_limit=10)
    cache.put(tenant_id="t1", user_id="u1", rec_id="r1", rec_payload={"rec_id":"r1"}, config_fp="a")
    assert cache.get(tenant_id="t1", rec_id="r1", expected_config_fp="a") is not None
    assert cache.get(tenant_id="t1", rec_id="r1", expected_config_fp="b") is None
