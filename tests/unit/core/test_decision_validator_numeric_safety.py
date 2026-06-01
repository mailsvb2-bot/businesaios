from core.constraints.decision import DecisionConstraints
from core.contracts.decision_candidate import DecisionCandidate
from core.policy.decision_validator import DecisionValidator


def test_decision_validator_handles_non_numeric_payload_values() -> None:
    candidate = DecisionCandidate(
        action_type='route_lead',
        channel='crm',
        score=0.5,
        expected_value=0.5,
        confidence=0.8,
        payload={'budget_delta': 'oops', 'risk_score': 'NaN', 'business_id': 'biz-1'},
    )
    ok, reason = DecisionValidator().validate(candidate, DecisionConstraints())
    assert ok is True
    assert reason == 'ok'
