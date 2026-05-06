from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_policy import MarketIntelligencePolicy


def test_policy_rejects_mismatched_action_family() -> None:
    policy = MarketIntelligencePolicy()
    request = MarketIntelligenceIngestionRequest(
        tenant_id='t1',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_ads_library',
    )
    try:
        policy.validate_request(request)
    except ValueError as exc:
        assert 'mismatch' in str(exc)
    else:
        raise AssertionError('policy must reject mismatched action/family')
