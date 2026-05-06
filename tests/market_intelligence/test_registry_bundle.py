from connectors.platform.market_intelligence.registry_bundle import build_market_intelligence_registry_entries


def test_market_intelligence_registry_bundle_has_all_connectors() -> None:
    entries = build_market_intelligence_registry_entries()
    assert len(entries) >= 47
    connector_ids = {entry.connector_id for entry in entries}
    assert 'amazon' in connector_ids
    assert 'facebook_ad_library' in connector_ids
    assert 'google_trends' in connector_ids
    assert 'mailchimp_public' in connector_ids
