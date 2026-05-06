from core.contracts.decision_candidate import DecisionCandidate
from core.constraints.decision import DecisionConstraints
from core.policy.decision_validator import DecisionValidator


def test_decision_validator_requires_business_id_for_route_lead() -> None:
    ok, reason = DecisionValidator().validate(
        DecisionCandidate(action_type='route_lead', channel='crm', score=0.5, expected_value=0.5, confidence=0.9, payload={}),
        DecisionConstraints(),
    )
    assert ok is False
    assert reason == 'missing_business_id'
