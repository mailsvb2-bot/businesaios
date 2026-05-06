from attribution.attribution_engine import AttributionEngine


def test_attribution_engine_returns_result():
    result = AttributionEngine().attribute({'channel': 'ads'})
    assert result['kind'] == 'attribution_result'
