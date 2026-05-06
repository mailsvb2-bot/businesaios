from contracts.platforms.market_intelligence_advanced_contract import UnifiedSignal
from execution.market_intelligence_opportunity_detector import OpportunityDetector
from execution.market_intelligence_scoring import EvidenceScoringEngine


def test_scoring_engine_produces_structured_importance():
    signals = [
        UnifiedSignal(tenant_id='t1', entity_id='crm', entity_kind='product', source_family='search_intelligence', provider='google', signal_kind='demand', observed_at='2026-04-08T00:00:00+00:00', confidence=0.8, strength=0.9, freshness=1.0, frequency=0.5),
        UnifiedSignal(tenant_id='t1', entity_id='crm', entity_kind='product', source_family='marketplace', provider='amazon', signal_kind='pricing', observed_at='2026-04-08T00:00:00+00:00', confidence=0.7, strength=0.8, freshness=1.0, frequency=0.4),
    ]
    scores = EvidenceScoringEngine().score(signals)
    assert scores and scores[0].structured_importance > 0.6


def test_opportunity_detector_emits_rising_demand():
    signals = [
        UnifiedSignal(tenant_id='t1', entity_id='crm', entity_kind='product', source_family='search_intelligence', provider='google', signal_kind='demand', observed_at='2026-04-08T00:00:00+00:00', confidence=0.9, strength=0.9, freshness=1.0, frequency=0.5, payload={'title': 'CRM'}),
        UnifiedSignal(tenant_id='t1', entity_id='crm', entity_kind='product', source_family='marketplace', provider='amazon', signal_kind='demand', observed_at='2026-04-08T00:00:00+00:00', confidence=0.8, strength=0.8, freshness=1.0, frequency=0.5, payload={'title': 'CRM'}),
    ]
    opportunities = OpportunityDetector().detect(signals)
    assert any(item.opportunity_type == 'rising_demand' for item in opportunities)
