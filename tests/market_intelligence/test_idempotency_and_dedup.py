from execution.market_intelligence_dedup import MarketIntelligenceDeduplicator
from execution.market_intelligence_idempotency import build_market_intelligence_idempotency_key
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest


def test_idempotency_key_is_stable() -> None:
    request = MarketIntelligenceIngestionRequest(
        tenant_id='tenant-a',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_marketplace_catalog',
        query='hypnosis',
    )
    assert build_market_intelligence_idempotency_key(request) == build_market_intelligence_idempotency_key(request)


def test_deduplicator_removes_duplicates() -> None:
    records = [
        {'provider': 'amazon', 'external_id': '1', 'title': 'A'},
        {'provider': 'amazon', 'external_id': '1', 'title': 'B'},
        {'provider': 'amazon', 'external_id': '2', 'title': 'C'},
    ]
    deduped = MarketIntelligenceDeduplicator().deduplicate(records)
    assert len(deduped) == 2
