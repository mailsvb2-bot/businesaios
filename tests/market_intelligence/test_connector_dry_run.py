from interfaces.market_intelligence.amazon import AmazonConnector


def test_market_intel_dry_run_works_without_provider_client() -> None:
    connector = AmazonConnector()
    result = connector.execute('sync_catalog', {'tenant_id': 't1', 'query': 'vitamins'}, dry_run=True)
    assert result.ok is True
    assert result.code == 'dry_run'
    assert result.payload['source_family'] == 'marketplace'
    assert result.payload['provider'] == 'amazon'
