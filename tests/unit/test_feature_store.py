from ml.common.feature_store import FeatureStore


def test_feature_store_returns_feature_vector():
    store = FeatureStore()
    store.put('lead_1', {'expected_value': 12, 'flag': True})
    vector = store.get('lead_1')
    assert vector.values['expected_value'] == 12.0
    assert vector.values['flag'] == 1.0
