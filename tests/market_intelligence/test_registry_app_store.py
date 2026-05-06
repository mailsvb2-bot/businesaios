from connectors.platform.market_intelligence.registry_bundle import build_market_intelligence_registry_entries


def test_registry_bundle_contains_apple_app_store() -> None:
    entries = build_market_intelligence_registry_entries()
    ids = {entry.connector_id for entry in entries}
    assert 'apple_app_store' in ids
