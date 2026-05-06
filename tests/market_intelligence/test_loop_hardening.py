from execution.market_intelligence_loop import MarketIntelligenceLoop
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest


def test_loop_applies_idempotency_and_normalization() -> None:
    calls = {'count': 0}

    def execute_action(action_type: str, payload: dict[str, object]) -> dict[str, object]:
        calls['count'] += 1
        return {
            'records': [
                {'provider': 'amazon', 'external_id': '1', 'title': '  Test   product ', 'body': ' hello   world '},
                {'provider': 'amazon', 'external_id': '1', 'title': 'Duplicate', 'body': 'ignored'},
            ]
        }

    loop = MarketIntelligenceLoop(execute_action=execute_action)
    request = MarketIntelligenceIngestionRequest(
        tenant_id='tenant-a',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_marketplace_catalog',
    )
    first = loop.run(request)
    second = loop.run(request)
    assert calls['count'] == 1
    assert len(first['records']) == 1
    assert second['idempotency_hit'] is True
