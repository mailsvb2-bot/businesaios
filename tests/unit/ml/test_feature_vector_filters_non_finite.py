from ml.common.feature_vector import FeatureVector


def test_feature_vector_drops_non_finite_values() -> None:
    vector = FeatureVector.from_mapping({'ok': 1.0, 'bad': float('nan')})
    assert vector.values == {'ok': 1.0}
