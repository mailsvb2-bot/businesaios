from execution.market_intelligence_action_specs import build_market_intelligence_action_specs


def test_market_intelligence_action_specs_cover_all_families() -> None:
    specs = build_market_intelligence_action_specs()
    assert len(specs) == 12
    assert 'sync_marketplace_catalog' in specs
    assert 'sync_newsletter_intelligence' in specs
