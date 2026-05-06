from onboarding import ActivationFlow


def test_activation_flow_returns_payload():
    result = ActivationFlow().build({'business_id': 'b1'})
    assert result['kind'] == 'activation_flow'
