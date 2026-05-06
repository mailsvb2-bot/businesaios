from ml.common.inference_contract import InferenceContract


def test_inference_contract_rejects_non_finite_features() -> None:
    contract = InferenceContract(model_name='m1', entity_id='e1', features={'x': float('inf')})
    assert 'non_finite_feature:x' in contract.validate()
