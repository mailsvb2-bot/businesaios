from core.contracts.decision_candidate import DecisionCandidate


def test_decision_candidate_rejects_non_finite_score() -> None:
    candidate = DecisionCandidate(action_type='route_lead', channel='crm', score=float('nan'), expected_value=1.0, confidence=0.9)
    assert 'invalid_score' in candidate.validate()
