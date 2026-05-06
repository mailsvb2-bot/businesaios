from execution.market_intelligence_circuit_breaker import MarketIntelligenceCircuitBreaker
from execution.market_intelligence_governance import MarketIntelligenceGovernance
from execution.market_intelligence_idempotency import MarketIntelligenceIdempotencyStore
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_normalizer import MarketIntelligenceRecordNormalizer
from execution.market_intelligence_quota_guard import MarketIntelligenceQuotaGuard


def test_quota_guard_tracks_provider_and_family_scopes() -> None:
    guard = MarketIntelligenceQuotaGuard(max_requests_per_tenant=10, max_requests_per_provider=1, max_requests_per_family=2)
    req = MarketIntelligenceIngestionRequest(
        tenant_id='t1',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_marketplace_catalog',
    )
    guard.consume(req)
    try:
        guard.consume(req)
    except ValueError as exc:
        assert 'provider quota exceeded' in str(exc)
    else:
        raise AssertionError('expected provider quota error')


def test_circuit_breaker_half_open_budget_is_enforced() -> None:
    breaker = MarketIntelligenceCircuitBreaker(failure_threshold=2, half_open_after_failures=1)
    breaker.on_failure('amazon')
    breaker.on_failure('amazon')
    breaker.ensure_open('amazon')
    try:
        breaker.ensure_open('amazon')
    except ValueError as exc:
        assert 'provider circuit open' in str(exc)
    else:
        raise AssertionError('expected open circuit')


def test_idempotency_store_returns_deep_copy() -> None:
    store = MarketIntelligenceIdempotencyStore(max_entries=10)
    store.put('k1', {'records': [{'title': 'A'}]})
    cached = store.get('k1')
    assert cached is not None
    cached['records'][0]['title'] = 'B'
    again = store.get('k1')
    assert again == {'records': [{'title': 'A'}]}


def test_normalizer_clamps_rating_and_invalid_url() -> None:
    normalizer = MarketIntelligenceRecordNormalizer()
    row = normalizer.normalize_record({'rating': 9, 'url': 'ftp://bad', 'price': -3})
    assert row['rating'] == 5.0
    assert row['url'] is None
    assert row['price'] == 0.0


def test_governance_caps_limit_without_tenancy_scope() -> None:
    governance = MarketIntelligenceGovernance(default_scope_max_limit=20)
    req = MarketIntelligenceIngestionRequest(
        tenant_id='t1',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_marketplace_catalog',
        limit=100,
    )
    scoped, risk = governance.enforce(req)
    assert scoped.limit == 20
    assert risk['risk_level'] == 'normal'
