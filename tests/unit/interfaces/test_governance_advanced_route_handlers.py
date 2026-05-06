from interfaces.api.governance_advanced_models import (
    JoinedHistoryResponse,
    PromotionEvidenceVerifyResponse,
    RollbackRecommendationRequest,
    RollbackRecommendationResponse,
)
from interfaces.api.governance_advanced_route_handlers import GovernanceAdvancedRouteHandlers


def test_governance_advanced_handlers_construct_response_types(monkeypatch) -> None:
    handlers = GovernanceAdvancedRouteHandlers()
    monkeypatch.setattr(handlers, '_governance', type('G', (), {
        'rollback_recommendation': staticmethod(lambda **_: {'baseline_name': 'b', 'candidate_run_id': 'c', 'should_rollback': True, 'confidence': 0.9, 'reason': 'high_drift', 'recommended_run_id': 'r'}),
        'joined_history': staticmethod(lambda **_: {'payload': True}),
        'verify_promotion_evidence': staticmethod(lambda **_: {'ok': True, 'expected': {}, 'observed': {}}),
    })())
    assert isinstance(handlers.rollback_recommendation(RollbackRecommendationRequest(baseline_name='b', candidate_run_id='c', fallback_run_ids=['r'])), RollbackRecommendationResponse)
    assert isinstance(handlers.joined_history(type('R', (), {'baseline_name': 'b', 'candidate_run_ids': ['c']})()), JoinedHistoryResponse)
    assert isinstance(handlers.verify_promotion_evidence(type('R', (), {'baseline_name': 'b'})()), PromotionEvidenceVerifyResponse)
