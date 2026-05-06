from ml.common.feature_vector import FeatureVector
from ml.common.inference_contract import InferenceContract
from ml.scoring.base_score_model import BaseScoreModel


def test_feature_vector_filters_non_numeric_values():
    vector = FeatureVector.from_mapping({'x': 1, 'flag': True, 'bad': 'oops'})
    assert vector.values == {'x': 1.0, 'flag': 1.0}


def test_inference_contract_rejects_non_numeric_features():
    contract = InferenceContract(model_name='m', entity_id='e', features={'x': 'bad'})
    assert contract.validate() == ['non_numeric_feature:x']


def test_base_score_model_uses_safe_numbers():
    model = BaseScoreModel(model_name='m', feature_weights={'x': 0.5})
    result = model.score({'x': 'bad', 'confidence': 'bad'})
    assert 0.0 <= result.score <= 1.0
    assert 0.0 <= result.confidence <= 1.0
