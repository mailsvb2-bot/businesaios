from growth.core.growth_engine import GrowthEngine


def test_growth_engine_builds_candidates_from_signals():
    engine = GrowthEngine()
    candidates = engine.assemble_opportunities([{'channel': 'ads', 'score': 0.7, 'expected_value': 9.0, 'confidence': 0.8}])
    assert candidates[0].channel == 'ads'
    assert 'risk_score' in candidates[0].payload
