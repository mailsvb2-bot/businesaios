from core.contracts.decision_candidate import DecisionCandidate
from ml.explainability.opportunity_explainer import OpportunityExplainer


def test_opportunity_explainer_redacts_sensitive_payload() -> None:
    candidate = DecisionCandidate(
        action_type='route_lead',
        channel='email',
        score=0.8,
        expected_value=0.8,
        confidence=0.9,
        payload={'phone': '+123', 'email': 'a@example.com', 'business_id': 'biz-1'},
    )
    payload = OpportunityExplainer().explain(candidate)['payload']
    assert payload['phone'] == '<redacted>'
    assert payload['email'] == '<redacted>'
    assert payload['business_id'] == 'biz-1'
