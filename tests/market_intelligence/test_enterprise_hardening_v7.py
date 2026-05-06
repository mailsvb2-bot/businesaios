from execution.market_intelligence_connector_resolver import MarketIntelligenceConnectorResolver
from execution.market_intelligence_effector_catalog import build_market_intelligence_effector
from execution.market_intelligence_loop import MarketIntelligenceExecutionError, MarketIntelligenceLoop
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_observability import MarketIntelligenceTelemetry
from execution.market_intelligence_retry_policy import MarketIntelligenceRetryPolicy
from interfaces.market_intelligence.amazon import AmazonConnector
from interfaces.market_intelligence.facebook_ad_library import FacebookAdLibraryConnector


def test_retry_policy_accepts_temporary_unavailable() -> None:
    policy = MarketIntelligenceRetryPolicy()
    assert policy.should_retry(attempt=1, code='temporary_unavailable') is True


def test_idempotency_hit_does_not_consume_quota_twice() -> None:
    calls: list[dict] = []

    def execute_action(action_type: str, payload: dict):
        calls.append({'action_type': action_type, 'payload': dict(payload)})
        return {
            'ok': True,
            'executed': True,
            'records': [{'provider': 'amazon', 'source_family': 'marketplace', 'external_id': 'sku-1', 'title': 'A'}],
        }

    loop = MarketIntelligenceLoop(execute_action=execute_action)
    request = MarketIntelligenceIngestionRequest(
        tenant_id='tenant-a',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_marketplace_catalog',
        query='chairs',
    )
    first = loop.run(request)
    second = loop.run(request)
    assert first['idempotency_hit'] is False
    assert second['idempotency_hit'] is True
    assert len(calls) == 1
    assert second['quota_snapshot']['tenant']['tenant-a'] == 1


def test_loop_raises_on_not_ok_result_payload() -> None:
    def execute_action(action_type: str, payload: dict):
        return {'ok': False, 'code': 'temporary_unavailable', 'message': 'upstream timeout'}

    loop = MarketIntelligenceLoop(execute_action=execute_action)
    request = MarketIntelligenceIngestionRequest(
        tenant_id='tenant-a',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_marketplace_catalog',
        query='chairs',
    )
    try:
        loop.run(request)
    except MarketIntelligenceExecutionError as exc:
        assert exc.code == 'temporary_unavailable'
    else:
        raise AssertionError('expected MarketIntelligenceExecutionError')


def test_telemetry_is_bounded() -> None:
    telemetry = MarketIntelligenceTelemetry(max_events=3)
    for idx in range(5):
        telemetry.emit('evt', n=idx)
    snapshot = telemetry.snapshot()
    assert len(snapshot['events']) == 3
    assert snapshot['events'][0]['payload']['n'] == 2


def test_provider_routed_effector_uses_requested_provider() -> None:
    effector = build_market_intelligence_effector(action_type='sync_ads_library')
    result = effector.execute({'payload': {'provider': 'facebook_ad_library', 'dry_run': True}})
    assert result.executed is True
    connector_payload = result.payload['connector_payload']
    assert connector_payload['provider'] == 'meta'


def test_connector_resolver_covers_multiple_families() -> None:
    resolver = MarketIntelligenceConnectorResolver()
    assert isinstance(resolver.build('amazon'), AmazonConnector)
    assert isinstance(resolver.build('facebook_ad_library'), FacebookAdLibraryConnector)
