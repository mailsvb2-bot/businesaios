from ml.common.inference_contract import InferenceContract


def test_inference_contract_rejects_empty_feature_key() -> None:
    issues = InferenceContract(model_name='m', entity_id='e', features={'': 1.0}).validate()
    assert 'empty_feature_key' in issues
