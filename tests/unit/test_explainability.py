from core.contracts.decision_candidate import DecisionCandidate
from ml.explainability.opportunity_explainer import OpportunityExplainer


def test_opportunity_explainer_exposes_candidate_id_and_payload():
    candidate = DecisionCandidate('notify_owner', 'internal', 0.8, 10.0, 0.9, payload={'risk_score': 0.1})
    payload = OpportunityExplainer().explain(candidate)
    assert payload['candidate_id'] == candidate.candidate_id
    assert payload['payload']['risk_score'] == 0.1
