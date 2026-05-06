from ml.common.inference_contract import InferenceContract


def test_inference_contract_rejects_non_string_context_values() -> None:
    issues = InferenceContract(model_name='m', entity_id='e', features={'x': 1.0}, context={'tenant': 1}).validate()
    assert 'non_string_context:tenant' in issues
